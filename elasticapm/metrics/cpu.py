import platform

if platform.system() == "Linux":
    from elasticapm.metrics.cpu_linux import CPUMetricSet  # noqa: F401
else:
    from elasticapm.metrics.cpu_psutil import CPUMetricSet  # noqa: F401
