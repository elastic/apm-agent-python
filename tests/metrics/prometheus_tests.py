#  BSD 3-Clause License
#
#  Copyright (c) 2021, Elasticsearch BV
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
import platform

import pytest

prometheus_client = pytest.importorskip("prometheus_client")

from elasticapm.metrics.base_metrics import MetricsRegistry
from elasticapm.metrics.sets.prometheus import PrometheusMetrics

pytestmark = pytest.mark.prometheus_client


prometheus_client.REGISTRY.unregister(prometheus_client.PROCESS_COLLECTOR)
prometheus_client.REGISTRY.unregister(prometheus_client.PLATFORM_COLLECTOR)
if platform.python_implementation() == "CPython":
    prometheus_client.REGISTRY.unregister(prometheus_client.GC_COLLECTOR)


@pytest.fixture()
def prometheus():
    # reset registry
    prometheus_client.REGISTRY._collector_to_names = {}
    prometheus_client.REGISTRY._names_to_collectors = {}


def test_counter(elasticapm_client, prometheus):
    metricset = PrometheusMetrics(MetricsRegistry(elasticapm_client))
    counter = prometheus_client.Counter("a_bare_counter", "Bare counter")
    counter_with_labels = prometheus_client.Counter(
        "counter_with_labels", "Counter with labels", ["alabel", "anotherlabel"]
    )
    counter.inc()
    counter_with_labels.labels(alabel="foo", anotherlabel="baz").inc()
    counter_with_labels.labels(alabel="bar", anotherlabel="bazzinga").inc()
    counter_with_labels.labels(alabel="foo", anotherlabel="baz").inc()
    data = list(metricset.collect())
    assert len(data) == 3
    assert data[0]["samples"]["prometheus.metrics.a_bare_counter"]["value"] == 1.0
    assert data[1]["samples"]["prometheus.metrics.counter_with_labels"]["value"] == 2.0
    assert data[1]["tags"] == {"alabel": "foo", "anotherlabel": "baz"}
    assert data[2]["samples"]["prometheus.metrics.counter_with_labels"]["value"] == 1.0
    assert data[2]["tags"] == {"alabel": "bar", "anotherlabel": "bazzinga"}


def test_gauge(elasticapm_client, prometheus):
    metricset = PrometheusMetrics(MetricsRegistry(elasticapm_client))
    gauge = prometheus_client.Gauge("a_bare_gauge", "Bare gauge")
    gauge_with_labels = prometheus_client.Gauge("gauge_with_labels", "Gauge with labels", ["alabel", "anotherlabel"])
    gauge.set(5)
    gauge_with_labels.labels(alabel="foo", anotherlabel="baz").set(7)
    gauge_with_labels.labels(alabel="bar", anotherlabel="bazzinga").set(11)
    gauge_with_labels.labels(alabel="foo", anotherlabel="baz").set(2)
    data = list(metricset.collect())
    assert len(data) == 3
    assert data[0]["samples"]["prometheus.metrics.a_bare_gauge"]["value"] == 5.0
    assert data[1]["samples"]["prometheus.metrics.gauge_with_labels"]["value"] == 2.0
    assert data[1]["tags"] == {"alabel": "foo", "anotherlabel": "baz"}
    assert data[2]["samples"]["prometheus.metrics.gauge_with_labels"]["value"] == 11.0
    assert data[2]["tags"] == {"alabel": "bar", "anotherlabel": "bazzinga"}


def test_summary(elasticapm_client, prometheus):
    metricset = PrometheusMetrics(MetricsRegistry(elasticapm_client))
    summary = prometheus_client.Summary("a_bare_summary", "Bare summary")
    summary_with_labels = prometheus_client.Summary(
        "summary_with_labels", "Summary with labels", ["alabel", "anotherlabel"]
    )
    summary.observe(5)
    summary.observe(7)
    summary.observe(9)
    summary_with_labels.labels(alabel="foo", anotherlabel="baz").observe(7)
    summary_with_labels.labels(alabel="bar", anotherlabel="bazzinga").observe(11)
    summary_with_labels.labels(alabel="foo", anotherlabel="baz").observe(2)
    data = list(metricset.collect())

    assert len(data) == 3
    assert data[0]["samples"]["prometheus.metrics.a_bare_summary.count"]["value"] == 3.0
    assert data[0]["samples"]["prometheus.metrics.a_bare_summary.sum"]["value"] == 21
    assert data[1]["samples"]["prometheus.metrics.summary_with_labels.count"]["value"] == 2.0
    assert data[1]["samples"]["prometheus.metrics.summary_with_labels.sum"]["value"] == 9.0
    assert data[1]["tags"] == {"alabel": "foo", "anotherlabel": "baz"}
    assert data[2]["samples"]["prometheus.metrics.summary_with_labels.count"]["value"] == 1.0
    assert data[2]["samples"]["prometheus.metrics.summary_with_labels.sum"]["value"] == 11.0
    assert data[2]["tags"] == {"alabel": "bar", "anotherlabel": "bazzinga"}


def test_histogram(elasticapm_client, prometheus):
    metricset = PrometheusMetrics(MetricsRegistry(elasticapm_client))
    histo = prometheus_client.Histogram("histo", "test histogram", buckets=[1, 10, 100, float("inf")])
    histo_with_labels = prometheus_client.Histogram(
        "histowithlabel", "test histogram with labels", ["alabel", "anotherlabel"], buckets=[1, 10, 100, float("inf")]
    )
    histo.observe(0.5)
    histo.observe(0.6)
    histo.observe(1.5)
    histo.observe(26)
    histo.observe(42)
    histo.observe(12)
    histo.observe(105)
    histo_with_labels.labels(alabel="foo", anotherlabel="baz").observe(1)
    histo_with_labels.labels(alabel="foo", anotherlabel="baz").observe(10)
    histo_with_labels.labels(alabel="foo", anotherlabel="baz").observe(100)
    histo_with_labels.labels(alabel="foo", anotherlabel="bazzinga").observe(1000)
    data = list(metricset.collect())
    assert data[0]["samples"]["prometheus.metrics.histo"]["values"] == [0.5, 5.5, 55.0, 100.0]
    assert data[0]["samples"]["prometheus.metrics.histo"]["counts"] == [2, 1, 3, 1]
    assert all(isinstance(v, int) for v in data[0]["samples"]["prometheus.metrics.histo"]["counts"])

    assert data[1]["samples"]["prometheus.metrics.histowithlabel"]["values"] == [0.5, 5.5, 55.0, 100.0]
    assert data[1]["samples"]["prometheus.metrics.histowithlabel"]["counts"] == [1, 1, 1, 0]
    assert all(isinstance(v, int) for v in data[1]["samples"]["prometheus.metrics.histowithlabel"]["counts"])
    assert data[1]["tags"] == {"alabel": "foo", "anotherlabel": "baz"}

    assert data[2]["samples"]["prometheus.metrics.histowithlabel"]["values"] == [0.5, 5.5, 55.0, 100.0]
    assert data[2]["samples"]["prometheus.metrics.histowithlabel"]["counts"] == [0, 0, 0, 1]
    assert all(isinstance(v, int) for v in data[2]["samples"]["prometheus.metrics.histowithlabel"]["counts"])
    assert data[2]["tags"] == {"alabel": "foo", "anotherlabel": "bazzinga"}
