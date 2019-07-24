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

import time

import pytest

from elasticapm.metrics.base_metrics import MetricsRegistry
from elasticapm.utils import compat

cpu_psutil = pytest.importorskip("elasticapm.metrics.sets.cpu_psutil")
pytestmark = pytest.mark.psutil


def test_cpu_mem_from_psutil():
    metricset = cpu_psutil.CPUMetricSet(MetricsRegistry(0, lambda x: None))
    # do something that generates some CPU load
    for i in compat.irange(10 ** 6):
        j = i * i
    data = next(metricset.collect())
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
    psutil_metricset = cpu_psutil.CPUMetricSet(MetricsRegistry(0, lambda x: None))
    linux_metricset = cpu_linux.CPUMetricSet(MetricsRegistry(0, lambda x: None))
    # do something that generates some CPU load
    for i in compat.irange(10 ** 6):
        j = i * i
    psutil_data = next(psutil_metricset.collect())
    linux_data = next(linux_metricset.collect())

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
