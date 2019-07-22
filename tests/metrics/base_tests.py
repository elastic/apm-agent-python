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

import threading
import time
from multiprocessing.dummy import Pool

import mock
import pytest

from elasticapm.conf import constants
from elasticapm.metrics.base_metrics import MetricsRegistry, MetricsSet
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
    time.sleep(0.1)
    assert mock_queue.call_count > 0
    registry._stop_collect_timer()


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


@mock.patch("elasticapm.base.MetricsRegistry._start_collect_timer")
@mock.patch("elasticapm.metrics.base_metrics.is_master_process")
def test_client_doesnt_start_collector_thread_in_master_process(is_master_process, mock_start_collect_timer):
    # when in the master process, the client should not start worker threads
    is_master_process.return_value = True
    before = mock_start_collect_timer.call_count
    client = TempStoreClient(server_url="http://example.com", service_name="app_name", secret_token="secret")
    assert mock_start_collect_timer.call_count == before
    client.close()

    before = mock_start_collect_timer.call_count
    is_master_process.return_value = False
    client = TempStoreClient(server_url="http://example.com", service_name="app_name", secret_token="secret")
    assert mock_start_collect_timer.call_count == before + 1
    client.close()
