import threading
import time
from multiprocessing.dummy import Pool

import mock

from elasticapm.metrics.base_metrics import MetricsRegistry, MetricsSet


class DummyMetricSet(object):
    def collect(self):
        return {"samples": []}


def test_metrics_registry():
    mock_queue = mock.Mock()
    registry = MetricsRegistry(0.001, queue_func=mock_queue)
    registry.register("tests.metrics.base_tests.DummyMetricSet")
    time.sleep(0.1)
    assert mock_queue.call_count > 0
    registry._stop_collect_timer()


def test_metrics_counter():
    metricset = MetricsSet()
    metricset.counter("x").inc()
    data = metricset.collect()
    assert data["samples"]["x"]["value"] == 1
    metricset.counter("x").inc(10)
    data = metricset.collect()
    assert data["samples"]["x"]["value"] == 11
    metricset.counter("x").dec(10)
    data = metricset.collect()
    assert data["samples"]["x"]["value"] == 1
    metricset.counter("x").dec()
    data = metricset.collect()
    assert data["samples"]["x"]["value"] == 0


def test_metrics_multithreaded():
    metricset = MetricsSet()
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
