import os
import re
import resource
import threading

from elasticapm.metrics.base_metrics import MetricsSet

SYS_STATS = "/proc/stat"
MEM_STATS = "/proc/meminfo"
PROC_STATS = "/proc/self/stat"

whitespace_re = re.compile(r"\s+")


if not os.path.exists(SYS_STATS):
    raise ImportError("This metric set is only available on Linux")


class CPUMetricSet(MetricsSet):
    def __init__(self, sys_stats_file=SYS_STATS, process_stats_file=PROC_STATS, memory_stats_file=MEM_STATS):
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
        super(CPUMetricSet, self).__init__()

    def collect(self):
        new = self.read_process_stats()
        new.update(self.read_system_stats())
        with self._read_data_lock:
            prev = self.previous
            delta = {k: new[k] - prev[k] for k in new.keys()}
            cpu_usage_ratio = delta["cpu_usage"] / delta["cpu_total"]
            self.gauge("system.cpu.total.norm.pct").val = cpu_usage_ratio
            self.gauge("system.memory.actual.free").val = new["mem_available"]
            self.gauge("system.memory.total").val = new["mem_total"]

            cpu_process_percent = delta["proc_total_time"] / delta["cpu_total"]

            self.gauge("system.process.cpu.total.norm.pct").val = cpu_process_percent
            self.gauge("system.process.memory.size").val = new["vsize"]
            self.gauge("system.process.memory.rss.bytes").val = new["rss"] * self.page_size
            self.previous = new
        return super(CPUMetricSet, self).collect()

    def read_system_stats(self):
        stats = {}
        with open(self.sys_stats_file, "r") as pidfile:
            for line in pidfile:
                if line.startswith("cpu "):
                    user, nice, system, idle, iowait, irq, softirq, steal, guest, guest_nice = map(
                        int, whitespace_re.split(line)[1:-1]
                    )
                    stats["cpu_total"] = float(user + nice + system + idle + iowait + irq + softirq + steal)
                    stats["cpu_usage"] = stats["cpu_total"] - (idle + iowait)
                    break
        with open(self.memory_stats_file, "r") as memfile:
            for line in memfile:
                if line.startswith("MemTotal:"):
                    stats["mem_total"] = int(whitespace_re.split(line)[1]) * 1024
                elif line.startswith("MemAvailable:"):
                    stats["mem_available"] = int(whitespace_re.split(line)[1]) * 1024
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
