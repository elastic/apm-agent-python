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
import time
from multiprocessing.dummy import Pool

import mock
import pytest

from elasticapm.conf import constants
from elasticapm.metrics.base_metrics import Counter, Gauge, MetricsRegistry, MetricsSet, NoopMetric, Timer
from tests.fixtures import TempStoreClient


class DummyMetricSet(MetricsSet):
    def before_collect(self):
        self.gauge("a.b.c.d").val = 0
        self.gauge("a").val = 0
        self.gauge("b").val = 0
        self.gauge("c").val = 0


def test_metrics_registry():
    mock_queue = mock.Mock()
    registry = MetricsRegistry(0.001, queue_func=mock_queue)
    registry.register("tests.metrics.base_tests.DummyMetricSet")
    try:
        registry.start_thread()
        time.sleep(0.1)
        assert mock_queue.call_count > 0
    finally:
        registry.stop_thread()


@pytest.mark.parametrize(
    "elasticapm_client",
    [{"metrics_sets": "tests.metrics.base_tests.DummyMetricSet", "disable_metrics": "a.*,*c"}],
    indirect=True,
)
def test_disable_metrics(elasticapm_client):
    elasticapm_client._metrics.collect()
    metrics = elasticapm_client.events[constants.METRICSET][0]
    assert "a" in metrics["samples"]
    assert "b" in metrics["samples"]
    assert "a.b.c.d" not in metrics["samples"]
    assert "c" not in metrics["samples"]


def test_metrics_counter():
    metricset = MetricsSet(MetricsRegistry(0, lambda x: None))
    metricset.counter("x").inc()
    data = next(metricset.collect())
    assert data["samples"]["x"]["value"] == 1
    metricset.counter("x").inc(10)
    data = next(metricset.collect())
    assert data["samples"]["x"]["value"] == 11
    metricset.counter("x").dec(10)
    data = next(metricset.collect())
    assert data["samples"]["x"]["value"] == 1
    metricset.counter("x").dec()
    data = next(metricset.collect())
    assert data["samples"]["x"]["value"] == 0


def test_metrics_labels():
    metricset = MetricsSet(MetricsRegistry(0, lambda x: None))
    metricset.counter("x", mylabel="a").inc()
    metricset.counter("y", mylabel="a").inc()
    metricset.counter("x", mylabel="b").inc().inc()
    metricset.counter("x", mylabel="b", myotherlabel="c").inc()
    metricset.counter("x", mylabel="a").dec()
    data = list(metricset.collect())
    asserts = 0
    for d in data:
        if d["tags"] == {"mylabel": "a"}:
            assert d["samples"]["x"]["value"] == 0
            assert d["samples"]["y"]["value"] == 1
            asserts += 1
        elif d["tags"] == {"mylabel": "b"}:
            assert d["samples"]["x"]["value"] == 2
            asserts += 1
        elif d["tags"] == {"mylabel": "b", "myotherlabel": "c"}:
            assert d["samples"]["x"]["value"] == 1
            asserts += 1
    assert asserts == 3


def test_metrics_multithreaded():
    metricset = MetricsSet(MetricsRegistry(0, lambda x: None))
    pool = Pool(5)

    def target():
        for i in range(500):
            metricset.counter("x").inc(i + 1)
            time.sleep(0.0000001)

    [pool.apply_async(target, ()) for i in range(10)]
    pool.close()
    pool.join()
    expected = 10 * ((500 * 501) / 2)
    assert metricset.counter("x").val == expected


@mock.patch("elasticapm.metrics.base_metrics.DISTINCT_LABEL_LIMIT", 3)
def test_metric_limit(caplog):
    m = MetricsSet(MetricsRegistry(0, lambda x: None))
    with caplog.at_level(logging.WARNING, logger="elasticapm.metrics"):
        for i in range(2):
            counter = m.counter("counter", some_label=i)
            gauge = m.gauge("gauge", some_label=i)
            timer = m.timer("timer", some_label=i)
            if i == 0:
                assert isinstance(timer, Timer)
                assert isinstance(gauge, Gauge)
                assert isinstance(counter, Counter)
            else:
                assert isinstance(timer, NoopMetric)
                assert isinstance(gauge, NoopMetric)
                assert isinstance(counter, NoopMetric)

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert "The limit of 3 metricsets has been reached" in record.message


def test_metrics_not_collected_if_zero_and_reset():
    m = MetricsSet(MetricsRegistry(0, lambda x: None))
    counter = m.counter("counter", reset_on_collect=False)
    resetting_counter = m.counter("resetting_counter", reset_on_collect=True)
    gauge = m.gauge("gauge", reset_on_collect=False)
    resetting_gauge = m.gauge("resetting_gauge", reset_on_collect=True)
    timer = m.timer("timer", reset_on_collect=False)
    resetting_timer = m.timer("resetting_timer", reset_on_collect=True)

    counter.inc(), resetting_counter.inc()
    gauge.val = 5
    resetting_gauge.val = 5
    timer.update(1, 1)
    resetting_timer.update(1, 1)

    data = list(m.collect())
    more_data = list(m.collect())
    assert set(data[0]["samples"].keys()) == {
        "counter",
        "resetting_counter",
        "gauge",
        "resetting_gauge",
        "timer.count",
        "timer.sum.us",
        "resetting_timer.count",
        "resetting_timer.sum.us",
    }
    assert set(more_data[0]["samples"].keys()) == {"counter", "gauge", "timer.count", "timer.sum.us"}
