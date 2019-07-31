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
import re
import resource
import threading

from elasticapm.metrics.base_metrics import MetricsSet

SYS_STATS = "/proc/stat"
MEM_STATS = "/proc/meminfo"
PROC_STATS = "/proc/self/stat"

CPU_FIELDS = ("user", "nice", "system", "idle", "iowait", "irq", "softirq", "steal", "guest", "guest_nice")
MEM_FIELDS = ("MemTotal", "MemAvailable", "MemFree", "Buffers", "Cached")

whitespace_re = re.compile(r"\s+")


if not os.path.exists(SYS_STATS):
    raise ImportError("This metric set is only available on Linux")


class CPUMetricSet(MetricsSet):
    def __init__(self, registry, sys_stats_file=SYS_STATS, process_stats_file=PROC_STATS, memory_stats_file=MEM_STATS):
        self.page_size = resource.getpagesize()
        self.previous = {}
        self._read_data_lock = threading.Lock()
        self.sys_stats_file = sys_stats_file
        self.process_stats_file = process_stats_file
        self.memory_stats_file = memory_stats_file
        self._sys_clock_ticks = os.sysconf("SC_CLK_TCK")
        with self._read_data_lock:
            self.previous.update(self.read_process_stats())
            self.previous.update(self.read_system_stats())
        super(CPUMetricSet, self).__init__(registry)

    def before_collect(self):
        new = self.read_process_stats()
        new.update(self.read_system_stats())
        with self._read_data_lock:
            prev = self.previous
            delta = {k: new[k] - prev[k] for k in new.keys()}
            cpu_usage_ratio = delta["cpu_usage"] / delta["cpu_total"]
            self.gauge("system.cpu.total.norm.pct").val = cpu_usage_ratio
            # MemAvailable not present in linux before kernel 3.14
            # fallback to MemFree + Buffers + Cache if not present - see #500
            if "MemAvailable" in new:
                mem_free = new["MemAvailable"]
            else:
                mem_free = sum(new.get(mem_field, 0) for mem_field in ("MemFree", "Buffers", "Cached"))
            self.gauge("system.memory.actual.free").val = mem_free
            self.gauge("system.memory.total").val = new["MemTotal"]

            cpu_process_percent = delta["proc_total_time"] / delta["cpu_total"]

            self.gauge("system.process.cpu.total.norm.pct").val = cpu_process_percent
            self.gauge("system.process.memory.size").val = new["vsize"]
            self.gauge("system.process.memory.rss.bytes").val = new["rss"] * self.page_size
            self.previous = new

    def read_system_stats(self):
        stats = {}
        with open(self.sys_stats_file, "r") as pidfile:
            for line in pidfile:
                if line.startswith("cpu "):
                    fields = whitespace_re.split(line)[1:-1]
                    num_fields = len(fields)
                    # Not all fields are available on all platforms (e.g. RHEL 6 does not provide steal, guest, and
                    # guest_nice. If a field is missing, we default to 0
                    f = {field: int(fields[i]) if i < num_fields else 0 for i, field in enumerate(CPU_FIELDS)}
                    stats["cpu_total"] = float(
                        f["user"]
                        + f["nice"]
                        + f["system"]
                        + f["idle"]
                        + f["iowait"]
                        + f["irq"]
                        + f["softirq"]
                        + f["steal"]
                    )
                    stats["cpu_usage"] = stats["cpu_total"] - (f["idle"] + f["iowait"])
                    break
        with open(self.memory_stats_file, "r") as memfile:
            for line in memfile:
                metric_name = line.split(":")[0]
                if metric_name in MEM_FIELDS:
                    value_in_bytes = int(whitespace_re.split(line)[1]) * 1024
                    stats[metric_name] = value_in_bytes
        return stats

    def read_process_stats(self):
        stats = {}
        with open(self.process_stats_file, "r") as pidfile:
            data = pidfile.readline().split(" ")
            stats["utime"] = int(data[13])
            stats["stime"] = int(data[14])
            stats["proc_total_time"] = stats["utime"] + stats["stime"]
            stats["vsize"] = int(data[22])
            stats["rss"] = int(data[23])
        return stats
