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

from elasticapm.metrics.base_metrics import MetricsSet

try:
    import psutil
except ImportError:
    raise ImportError("psutil not found. Install it to get system and process metrics")


class CPUMetricSet(MetricsSet):
    def __init__(self, registry):
        psutil.cpu_percent(interval=None)
        self._process = psutil.Process()
        self._process.cpu_percent(interval=None)
        super(CPUMetricSet, self).__init__(registry)

    def before_collect(self):
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
