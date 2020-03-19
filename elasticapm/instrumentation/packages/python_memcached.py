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

from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.traces import capture_span


class PythonMemcachedInstrumentation(AbstractInstrumentedModule):
    name = "python_memcached"

    method_list = [
        "add",
        "append",
        "cas",
        "decr",
        "delete",
        "delete_multi",
        "disconnect_all",
        "flush_all",
        "get",
        "get_multi",
        "get_slabs",
        "get_stats",
        "gets",
        "incr",
        "prepend",
        "replace",
        "set",
        "set_multi",
        "touch",
    ]
    # Took out 'set_servers', 'reset_cas', 'debuglog', 'check_key' and
    # 'forget_dead_hosts' because they involve no communication.

    def get_instrument_list(self):
        return [("memcache", "Client." + method) for method in self.method_list]

    def call(self, module, method, wrapped, instance, args, kwargs):
        name = self.get_wrapped_name(wrapped, instance, method)
        address, port = None, None
        if instance.servers:
            address, port = instance.servers[0].address
        destination = {
            "address": address,
            "port": port,
            "service": {"name": "memcached", "resource": "memcached", "type": "cache"},
        }
        with capture_span(
            name, span_type="cache", span_subtype="memcached", span_action="query", extra={"destination": destination}
        ):
            return wrapped(*args, **kwargs)
