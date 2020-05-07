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

try:
    from functools import lru_cache
except ImportError:
    from cachetools.func import lru_cache


class PyLibMcInstrumentation(AbstractInstrumentedModule):
    name = "pylibmc"

    instrument_list = [
        ("pylibmc", "Client.get"),
        ("pylibmc", "Client.get_multi"),
        ("pylibmc", "Client.set"),
        ("pylibmc", "Client.set_multi"),
        ("pylibmc", "Client.add"),
        ("pylibmc", "Client.replace"),
        ("pylibmc", "Client.append"),
        ("pylibmc", "Client.prepend"),
        ("pylibmc", "Client.incr"),
        ("pylibmc", "Client.decr"),
        ("pylibmc", "Client.gets"),
        ("pylibmc", "Client.cas"),
        ("pylibmc", "Client.delete"),
        ("pylibmc", "Client.delete_multi"),
        ("pylibmc", "Client.touch"),
        ("pylibmc", "Client.get_stats"),
    ]

    def call(self, module, method, wrapped, instance, args, kwargs):
        wrapped_name = self.get_wrapped_name(wrapped, instance, method)
        address, port = get_address_port_from_instance(instance)
        destination = {
            "address": address,
            "port": port,
            "service": {"name": "memcached", "resource": "memcached", "type": "cache"},
        }
        with capture_span(
            wrapped_name,
            span_type="cache",
            span_subtype="memcached",
            span_action="query",
            extra={"destination": destination},
        ):
            return wrapped(*args, **kwargs)


@lru_cache(10)
def get_address_port_from_instance(instance):
    address, port = None, None
    if instance.addresses:
        first_address = instance.addresses[0]
        if ":" in first_address:
            address, port = first_address.split(":", 1)
            try:
                port = int(port)
            except ValueError:
                port = None
    return address, port
