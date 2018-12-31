import os

import pytest

try:
    from elasticapm.metrics.sets.cpu_linux import CPUMetricSet
except ImportError:
    pytest.skip("Not a Linux system", allow_module_level=True)


TEMPLATE_PROC_STAT_SELF = """32677 (python) R 5333 32677 5333 34822 32677 4194304 13815 176 2 0 {utime} {stime} 0 0 20 0 7 0 6010710 3686981632 11655 18446744073709551615 94580847771648 94580849947501 140732830512176 0 0 0 0 16781312 134217730 0 0 0 17 1 0 0 6 0 0 94580850578256 94580851016824 94580875862016 140732830518932 140732830518950 140732830518950 140732830523339 0"""
TEMPLATE_PROC_STAT = """cpu  {user} 2037 278561 {idle} 15536 0 178811 0 0 0
cpu0 189150 166 34982 1081369 2172 0 73586 0 0 0
cpu1 190286 201 35110 637359 1790 0 41941 0 0 0
cpu2 191041 229 34494 636805 1782 0 21446 0 0 0
cpu3 192144 309 34143 635312 1808 0 16014 0 0 0
cpu4 190204 348 33770 636288 1880 0 9717 0 0 0
cpu5 188740 333 33741 638328 1899 0 6939 0 0 0
cpu6 188475 245 34417 635169 2323 0 3987 0 0 0
cpu7 184451 204 37902 638971 1879 0 5178 0 0 0
intr 60591079 11 12496 0 0 0 0 0 0 1 27128 0 0 474144 0 0 0 0 0 0 0 0 0 0 
ctxt 215687788
btime 1544981001
processes 416902
procs_running 3
procs_blocked 1
softirq 61270136 2508862 17040144 383 7315609 6627 56 23515 19184746 49637 15140557
"""
TEMPLATE_PROC_MEMINFO = """MemTotal:       16164884 kB
MemFree:          359184 kB
MemAvailable:    6514428 kB
Buffers:          891296 kB
Cached:          6416340 kB
SwapCached:          148 kB
Active:          7682276 kB
Inactive:        5468500 kB
"""


def test_cpu_mem_from_proc(tmpdir):
    proc_stat_self = os.path.join(tmpdir.strpath, "self-stat")
    proc_stat = os.path.join(tmpdir.strpath, "stat")
    proc_meminfo = os.path.join(tmpdir.strpath, "meminfo")

    for path, content in (
        (proc_stat, TEMPLATE_PROC_STAT.format(user=0, idle=0)),
        (proc_stat_self, TEMPLATE_PROC_STAT_SELF.format(utime=0, stime=0)),
        (proc_meminfo, TEMPLATE_PROC_MEMINFO),
    ):
        with open(path, mode="w") as f:
            f.write(content)
    metricset = CPUMetricSet(
        sys_stats_file=proc_stat, process_stats_file=proc_stat_self, memory_stats_file=proc_meminfo
    )

    for path, content in (
        (proc_stat, TEMPLATE_PROC_STAT.format(user=400000, idle=600000)),
        (proc_stat_self, TEMPLATE_PROC_STAT_SELF.format(utime=100000, stime=100000)),
        (proc_meminfo, TEMPLATE_PROC_MEMINFO),
    ):
        with open(path, mode="w") as f:
            f.write(content)
    data = metricset.collect()
    assert data["samples"]["system.cpu.total.norm.pct"]["value"] == 0.4
    assert data["samples"]["system.process.cpu.total.norm.pct"]["value"] == 0.2

    assert data["samples"]["system.memory.total"]["value"] == 16552841216
    assert data["samples"]["system.memory.actual.free"]["value"] == 6670774272

    assert data["samples"]["system.process.memory.rss.bytes"]["value"] == 47738880
    assert data["samples"]["system.process.memory.size"]["value"] == 3686981632
