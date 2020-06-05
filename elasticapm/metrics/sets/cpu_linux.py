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
CGROUP1_MEMORY_LIMIT = "memory.limit_in_bytes"
CGROUP1_MEMORY_USAGE = "memory.usage_in_bytes"
CGROUP2_MEMORY_LIMIT = "memory.max"
CGROUP2_MEMORY_USAGE = "memory.current"
UNLIMIT = 0x7FFFFFFFFFFFF000
PROC_SELF_CGROUP = "/proc/self/cgroup"
PROC_SELF_MOUNTINFO = "/proc/self/mountinfo"
SYS_FS_CGROUP = "/sys/fs/cgroup"

CPU_FIELDS = ("user", "nice", "system", "idle", "iowait", "irq", "softirq", "steal", "guest", "guest_nice")
MEM_FIELDS = ("MemTotal", "MemAvailable", "MemFree", "Buffers", "Cached")

whitespace_re = re.compile(r"\s+")

MEMORY_CGROUP = re.compile(r"^\d+\:memory\:.*")
CGROUP1_MOUNT_POINT = re.compile(r"^\d+? \d+? .+? .+? (.*?) .*cgroup.*cgroup.*memory.*")
CGROUP2_MOUNT_POINT = re.compile(r"^\d+? \d+? .+? .+? (.*?) .*cgroup2.*cgroup.*")

if not os.path.exists(SYS_STATS):
    raise ImportError("This metric set is only available on Linux")


class CPUMetricSet(MetricsSet):
    def __init__(
        self,
        registry,
        sys_stats_file=SYS_STATS,
        process_stats_file=PROC_STATS,
        memory_stats_file=MEM_STATS,
        procSelfCgroup=PROC_SELF_CGROUP,
        mountInfo=PROC_SELF_MOUNTINFO,
    ):
        self.page_size = resource.getpagesize()
        self.previous = {}
        self._read_data_lock = threading.Lock()
        self.sys_stats_file = sys_stats_file
        self.process_stats_file = process_stats_file
        self.memory_stats_file = memory_stats_file
        self._sys_clock_ticks = os.sysconf("SC_CLK_TCK")
        with self._read_data_lock:
            self.cgroupFiles = self.verifyCgroupEnabled(procSelfCgroup, mountInfo)
            self.previous.update(self.read_process_stats())
            self.previous.update(self.read_system_stats())
        super(CPUMetricSet, self).__init__(registry)

    def verifyCgroupEnabled(self, procSelfCgroup, mountInfo):
        try:
            lineCgroup = None
            with open(procSelfCgroup, "r") as procSelfCgroupFile:
                for line in procSelfCgroupFile:
                    if lineCgroup == None and line.startswith("0:"):
                        lineCgroup = line
                    if MEMORY_CGROUP.match(line):
                        lineCgroup = line
            if lineCgroup != None:
                with open(mountInfo, "r") as mountInfoFile:
                    for line in mountInfoFile:
                        matcher = CGROUP2_MOUNT_POINT.match(line)
                        if matcher != None:
                            cgroupFilesTest = self.verifyCgroup2Available(lineCgroup, matcher.group(1))
                            if cgroupFilesTest != None:
                                return cgroupFilesTest
                        matcher = CGROUP1_MOUNT_POINT.match(line)
                        if matcher != None:
                            cgroupFilesTest = self.verifyCgroup1Available(matcher.group(1))
                            if cgroupFilesTest != None:
                                return cgroupFilesTest
                cgroupFilesTest = self.verifyCgroup2Available(lineCgroup, SYS_FS_CGROUP)
                if cgroupFilesTest != None:
                    return cgroupFilesTest
                cgroupFilesTest = self.verifyCgroup1Available(SYS_FS_CGROUP + os.path.sep + "memory")
                if cgroupFilesTest != None:
                    return cgroupFilesTest
        except Exception:
            pass
        return None

    def verifyCgroup2Available(self, lineCgroup, mountDiscovered):
        try:
            lineSplit = lineCgroup.strip().split(":")
            slicePath = lineSplit[-1][1:]
            with open(os.path.join(mountDiscovered, slicePath, CGROUP2_MEMORY_LIMIT), "r") as memfile:
                lineMem = memfile.readline().strip()
                if lineMem != "max":
                    return (
                        os.path.join(mountDiscovered, slicePath, CGROUP2_MEMORY_LIMIT),
                        os.path.join(mountDiscovered, slicePath, CGROUP2_MEMORY_USAGE),
                    )
        except Exception:
            pass
        return None

    def verifyCgroup1Available(self, mountDiscovered):
        try:
            with open(os.path.join(mountDiscovered, CGROUP1_MEMORY_LIMIT), "r") as memfile:
                memMax = int(memfile.readline().strip())
                if memMax < UNLIMIT:
                    return (
                        os.path.join(mountDiscovered, CGROUP1_MEMORY_LIMIT),
                        os.path.join(mountDiscovered, CGROUP1_MEMORY_USAGE),
                    )
        except Exception:
            pass
        return None

    def before_collect(self):
        new = self.read_process_stats()
        new.update(self.read_system_stats())
        with self._read_data_lock:
            prev = self.previous
            delta = {k: new[k] - prev[k] for k in new.keys()}
            try:
                cpu_usage_ratio = delta["cpu_usage"] / delta["cpu_total"]
            except ZeroDivisionError:
                cpu_usage_ratio = 0
            self.gauge("system.cpu.total.norm.pct").val = cpu_usage_ratio
            # MemAvailable not present in linux before kernel 3.14
            # fallback to MemFree + Buffers + Cache if not present - see #500
            if "MemAvailable" in new:
                mem_free = new["MemAvailable"]
            else:
                mem_free = sum(new.get(mem_field, 0) for mem_field in ("MemFree", "Buffers", "Cached"))
            self.gauge("system.memory.actual.free").val = mem_free
            self.gauge("system.memory.total").val = new["MemTotal"]

            try:
                cpu_process_percent = delta["proc_total_time"] / delta["cpu_total"]
            except ZeroDivisionError:
                cpu_process_percent = 0

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
        if self.cgroupFiles != None:
            with open(self.cgroupFiles[0], "r") as memfile:
                stats["MemTotal"] = int(memfile.readline())
            with open(self.cgroupFiles[1], "r") as memfile:
                usage = int(memfile.readline())
                stats["MemAvailable"] = stats["MemTotal"] - usage
        else:
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
