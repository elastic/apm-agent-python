from elasticapm.metrics.base_metrics import MetricsSet

try:
    import psutil
except ImportError:
    raise ImportError("psutil not found. Install it to get system and process metrics")


class CPUMetricSet(MetricsSet):
    def __init__(self):
        psutil.cpu_percent(interval=None)
        self._process = psutil.Process()
        self._process.cpu_percent(interval=None)
        super(CPUMetricSet, self).__init__()

    def collect(self):
        self.gauge("system.cpu.total.norm.pct").val = psutil.cpu_percent(interval=None) / 100.0
        self.gauge("system.memory.actual.free").val = psutil.virtual_memory().available
        self.gauge("system.memory.total").val = psutil.virtual_memory().total
        p = self._process
        if hasattr(p, "oneshot"):  # new in psutil 5.0
            with p.oneshot():
                memory_info = p.memory_info()
                cpu_percent = p.cpu_percent(interval=None)
        else:
            memory_info = p.memory_info()
            cpu_percent = p.cpu_percent(interval=None)
        self.gauge("system.process.cpu.total.norm.pct").val = cpu_percent / 100.0 / psutil.cpu_count()
        self.gauge("system.process.memory.size").val = memory_info.vms
        self.gauge("system.process.memory.rss.bytes").val = memory_info.rss
        return super(CPUMetricSet, self).collect()
