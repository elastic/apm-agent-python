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

from __future__ import absolute_import

from elasticapm.contrib.asyncio.traces import async_capture_span
from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.traces import execution_context


class RedisConnectionPoolInstrumentation(AbstractInstrumentedModule):
    name = "aioredis"

    instrument_list = [("aioredis.pool", "ConnectionsPool.execute"),
                       ("aioredis.pool", "ConnectionsPool.execute_pubsub")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        if len(args) > 0:
            wrapped_name = args[0].decode()
        else:
            wrapped_name = self.get_wrapped_name(wrapped, instance, method)

        with async_capture_span(
            wrapped_name, span_type="db", span_subtype="redis", span_action="query", leaf=True
        ) as span:
            span.context["destination"] = _get_destination_info(instance)

            return wrapped(*args, **kwargs)


class RedisPipelineInstrumentation(AbstractInstrumentedModule):
    name = "aioredis"

    instrument_list = [("aioredis.commands.transaction", "Pipeline.execute")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        wrapped_name = self.get_wrapped_name(wrapped, instance, method)

        with async_capture_span(
            wrapped_name, span_type="db", span_subtype="redis", span_action="query", leaf=True
        ) as span:
            span.context["destination"] = _get_destination_info(instance)

            return wrapped(*args, **kwargs)


class RedisConnectionInstrumentation(AbstractInstrumentedModule):
    name = "aioredis"

    instrument_list = (("aioredis.connection", "RedisConnection.execute"),
                       ("aioredis.pool", "ConnectionsPool.execute_pubsub"))

    def call(self, module, method, wrapped, instance, args, kwargs):
        span = execution_context.get_span()
        if span and span.subtype == "aioredis":
            span.context["destination"] = _get_destination_info(instance)
        return wrapped(*args, **kwargs)


def _get_destination_info(connection):
    destination_info = {"service": {"name": "aioredis", "resource": "redis", "type": "db"}}

    if hasattr(connection, "_pool_or_conn"):
        destination_info["port"] = connection._pool_or_conn.address[1]
        destination_info["address"] = connection._pool_or_conn.address[0]
    else:
        destination_info["port"] = connection.address[1]
        destination_info["address"] = connection.address[0]

    return destination_info
