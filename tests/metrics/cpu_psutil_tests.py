import time

import pytest

from elasticapm.utils import compat

cpu_psutil = pytest.importorskip("elasticapm.metrics.sets.cpu_psutil")
pytestmark = pytest.mark.psutil


def test_cpu_mem_from_psutil():
    metricset = cpu_psutil.CPUMetricSet()
    # do something that generates some CPU load
    for i in compat.irange(10 ** 6):
        j = i * i
    data = metricset.collect()
    # we can't really test any specific values here as it depends on the system state.
    # Mocking is also not really a viable choice, as we would then lose the "integration testing"
    # nature of this test with different versions of psutil
    assert 0 < data["samples"]["system.cpu.total.norm.pct"]["value"] < 1
    assert 0 < data["samples"]["system.process.cpu.total.norm.pct"]["value"] < 1

    assert data["samples"]["system.memory.total"]["value"] > 0
    assert data["samples"]["system.memory.actual.free"]["value"] > 0

    assert data["samples"]["system.process.memory.rss.bytes"]["value"] > 0
    assert data["samples"]["system.process.memory.size"]["value"] > 0


cpu_linux = pytest.importorskip("elasticapm.metrics.sets.cpu_linux")


def test_compare_psutil_linux_metricsets():
    psutil_metricset = cpu_psutil.CPUMetricSet()
    linux_metricset = cpu_linux.CPUMetricSet()
    # do something that generates some CPU load
    for i in compat.irange(10 ** 6):
        j = i * i
    psutil_data = psutil_metricset.collect()
    linux_data = linux_metricset.collect()

    assert (
        abs(
            psutil_data["samples"]["system.cpu.total.norm.pct"]["value"]
            - linux_data["samples"]["system.cpu.total.norm.pct"]["value"]
        )
        < 0.02
    )
    assert (
        abs(
            psutil_data["samples"]["system.process.cpu.total.norm.pct"]["value"]
            - linux_data["samples"]["system.process.cpu.total.norm.pct"]["value"]
        )
        < 0.02
    )
