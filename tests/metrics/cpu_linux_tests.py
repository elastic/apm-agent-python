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

import os

import pytest

from elasticapm.metrics.base_metrics import MetricsRegistry

try:
    from elasticapm.metrics.sets.cpu_linux import CPUMetricSet
except ImportError:
    pytest.skip("Not a Linux system", allow_module_level=True)


TEMPLATE_PROC_STAT_SELF = """32677 (python) R 5333 32677 5333 34822 32677 4194304 13815 176 2 0 {utime} {stime} 0 0 20 0 7 0 6010710 3686981632 11655 18446744073709551615 94580847771648 94580849947501 140732830512176 0 0 0 0 16781312 134217730 0 0 0 17 1 0 0 6 0 0 94580850578256 94580851016824 94580875862016 140732830518932 140732830518950 140732830518950 140732830523339 0"""


TEMPLATE_PROC_STAT_DEBIAN = """cpu  {user} 2037 278561 {idle} 15536 0 178811 0 0 0
cpu0 189150 166 34982 1081369 2172 0 73586 0 0 0
cpu1 190286 201 35110 637359 1790 0 41941 0 0 0
intr 60591079 11 12496 0 0 0 0 0 0 1 27128 0 0 474144 0 0 0 0 0 0 0 0 0 0 
ctxt 215687788
btime 1544981001
processes 416902
procs_running 3
procs_blocked 1
softirq 61270136 2508862 17040144 383 7315609 6627 56 23515 19184746 49637 15140557
"""


TEMPLATE_PROC_STAT_RHEL = """cpu  {user} 2037 278561 {idle} 15536 0 178811
cpu0 259246 7001 60190 34250993 137517 772 0
intr 354133732 347209999 2272 0 4 4 0 0 3 1 1249247 0 0 80143 0 422626 5169433
ctxt 12547729
btime 1093631447
processes 130523
procs_running 1
procs_blocked 0"""


TEMPLATE_PROC_MEMINFO = """MemTotal:       16164884 kB
MemFree:          359184 kB
MemAvailable:    6514428 kB
Buffers:          891296 kB
Cached:          6416340 kB
SwapCached:          148 kB
Active:          7682276 kB
Inactive:        5468500 kB
"""


TEMPLATE_PROC_MEMINFO_NO_MEMAVAILABLE = """MemTotal:       16164884 kB
MemFree:          359184 kB
Buffers:          891296 kB
Cached:          6416340 kB
SwapCached:          148 kB
Active:          7682276 kB
Inactive:        5468500 kB
"""


@pytest.mark.parametrize("proc_stat_template", [TEMPLATE_PROC_STAT_DEBIAN, TEMPLATE_PROC_STAT_RHEL])
def test_cpu_mem_from_proc(proc_stat_template, tmpdir):
    proc_stat_self = os.path.join(tmpdir.strpath, "self-stat")
    proc_stat = os.path.join(tmpdir.strpath, "stat")
    proc_meminfo = os.path.join(tmpdir.strpath, "meminfo")

    for path, content in (
        (proc_stat, proc_stat_template.format(user=0, idle=0)),
        (proc_stat_self, TEMPLATE_PROC_STAT_SELF.format(utime=0, stime=0)),
        (proc_meminfo, TEMPLATE_PROC_MEMINFO),
    ):
        with open(path, mode="w") as f:
            f.write(content)
    metricset = CPUMetricSet(
        MetricsRegistry(0, lambda x: None),
        sys_stats_file=proc_stat,
        process_stats_file=proc_stat_self,
        memory_stats_file=proc_meminfo,
    )

    for path, content in (
        (proc_stat, proc_stat_template.format(user=400000, idle=600000)),
        (proc_stat_self, TEMPLATE_PROC_STAT_SELF.format(utime=100000, stime=100000)),
        (proc_meminfo, TEMPLATE_PROC_MEMINFO),
    ):
        with open(path, mode="w") as f:
            f.write(content)
    data = next(metricset.collect())
    assert data["samples"]["system.cpu.total.norm.pct"]["value"] == 0.4
    assert data["samples"]["system.process.cpu.total.norm.pct"]["value"] == 0.2

    assert data["samples"]["system.memory.total"]["value"] == 16552841216
    assert data["samples"]["system.memory.actual.free"]["value"] == 6670774272

    assert data["samples"]["system.process.memory.rss.bytes"]["value"] == 47738880
    assert data["samples"]["system.process.memory.size"]["value"] == 3686981632


def test_mem_free_from_memfree_when_memavailable_not_mentioned(tmpdir):
    proc_stat_self = os.path.join(tmpdir.strpath, "self-stat")
    proc_stat = os.path.join(tmpdir.strpath, "stat")
    proc_meminfo = os.path.join(tmpdir.strpath, "meminfo")

    for path, content in (
        (proc_stat, TEMPLATE_PROC_STAT_DEBIAN.format(user=0, idle=0)),
        (proc_stat_self, TEMPLATE_PROC_STAT_SELF.format(utime=0, stime=0)),
        (proc_meminfo, TEMPLATE_PROC_MEMINFO_NO_MEMAVAILABLE),
    ):
        with open(path, mode="w") as f:
            f.write(content)
    metricset = CPUMetricSet(
        MetricsRegistry(0, lambda x: None),
        sys_stats_file=proc_stat,
        process_stats_file=proc_stat_self,
        memory_stats_file=proc_meminfo,
    )

    for path, content in (
        (proc_stat, TEMPLATE_PROC_STAT_DEBIAN.format(user=400000, idle=600000)),
        (proc_stat_self, TEMPLATE_PROC_STAT_SELF.format(utime=100000, stime=100000)),
        (proc_meminfo, TEMPLATE_PROC_MEMINFO_NO_MEMAVAILABLE),
    ):
        with open(path, mode="w") as f:
            f.write(content)
    data = next(metricset.collect())

    mem_free_expected = sum([359184, 891296, 6416340]) * 1024  # MemFree + Buffers + Cached, in bytes
    assert data["samples"]["system.memory.actual.free"]["value"] == mem_free_expected


def test_cpu_usage_when_cpu_total_is_zero(tmpdir):
    proc_stat_self = os.path.join(tmpdir.strpath, "self-stat")
    proc_stat = os.path.join(tmpdir.strpath, "stat")
    proc_meminfo = os.path.join(tmpdir.strpath, "meminfo")

    for path, content in (
        (proc_stat, TEMPLATE_PROC_STAT_DEBIAN.format(user=0, idle=0)),
        (proc_stat_self, TEMPLATE_PROC_STAT_SELF.format(utime=0, stime=0)),
        (proc_meminfo, TEMPLATE_PROC_MEMINFO_NO_MEMAVAILABLE),
    ):
        with open(path, mode="w") as f:
            f.write(content)
    metricset = CPUMetricSet(
        MetricsRegistry(0, lambda x: None),
        sys_stats_file=proc_stat,
        process_stats_file=proc_stat_self,
        memory_stats_file=proc_meminfo,
    )
    data = next(metricset.collect())

    cpu_total_expected = 0
    assert data["samples"]["system.cpu.total.norm.pct"]["value"] == cpu_total_expected
    assert data["samples"]["system.process.cpu.total.norm.pct"]["value"] == cpu_total_expected
