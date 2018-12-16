from elasticapm.metrics.base_metrics import MetricsSet

try:
    import psutil
except ImportError:
    raise ImportError("psutil not found. Install it to get system and process metrics")


class CPUMetricSet(MetricsSet):
    def __init__(self):
        psutil.cpu_percent(interval=None)
        super(CPUMetricSet, self).__init__()

    def collect(self):
        cpu_count = float(psutil.cpu_count())
        self.gauge("system.cpu.total.norm.pct").val = psutil.cpu_percent(interval=None) / cpu_count
        self.gauge("system.memory.actual.free").val = psutil.virtual_memory().available
        self.gauge("system.memory.total").val = psutil.virtual_memory().total

        p = psutil.Process()
        with p.oneshot():
            memory_info = p.memory_full_info()
            self.gauge("system.process.cpu.total.norm.pct").val = p.cpu_percent() / cpu_count
            self.gauge("system.process.memory.size").val = memory_info.vms
            self.gauge("system.process.memory.rss.bytes").val = memory_info.rss
        return super(CPUMetricSet, self).collect()
