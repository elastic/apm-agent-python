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


class PyMemcacheInstrumentation(AbstractInstrumentedModule):
    name = "pymemcache"

    method_list = [
        "add",
        "append",
        "cas",
        "decr",
        "delete",
        "delete_many",
        "delete_multi",
        "flush_all",
        "get",
        "get_many",
        "get_multi",
        "gets",
        "gets_many",
        "incr",
        "prepend",
        "quit",
        "replace",
        "set",
        "set_many",
        "set_multi",
        "stats",
        "touch",
    ]

    def get_instrument_list(self):
        return (
            [("pymemcache.client.base", "Client." + method) for method in self.method_list]
            + [("pymemcache.client.base", "PooledClient." + method) for method in self.method_list]
            + [("pymemcache.client.hash", "HashClient." + method) for method in self.method_list]
        )

    def call(self, module, method, wrapped, instance, args, kwargs):
        name = self.get_wrapped_name(wrapped, instance, method)

        # Since HashClient uses Client/PooledClient for the actual calls, we
        # don't need to get address/port info for that class
        address, port = None, None
        if getattr(instance, "server", None):
            if isinstance(instance.server, (list, tuple)):
                # Address/port are a tuple
                address, port = instance.server
            else:
                # Server is a UNIX domain socket
                address = instance.server
        destination = {
            "address": address,
            "port": port,
            "service": {"name": "memcached", "resource": "memcached", "type": "cache"},
        }

        if "PooledClient" in name:
            # PooledClient calls out to Client for the "work", but only once,
            # so we don't care about the "duplicate" spans from Client in that
            # case
            with capture_span(
                name,
                span_type="cache",
                span_subtype="memcached",
                span_action="query",
                extra={"destination": destination},
                leaf=True,
            ):
                return wrapped(*args, **kwargs)
        else:
            with capture_span(
                name,
                span_type="cache",
                span_subtype="memcached",
                span_action="query",
                extra={"destination": destination},
            ):
                return wrapped(*args, **kwargs)
