import os
import platform

if platform.system() == "Linux" and "ELASTIC_APM_FORCE_PSUTIL_METRICS" not in os.environ:
    from elasticapm.metrics.cpu_linux import CPUMetricSet  # noqa: F401
else:
    from elasticapm.metrics.cpu_psutil import CPUMetricSet  # noqa: F401
