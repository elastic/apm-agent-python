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
from elasticapm.instrumentation.packages.asyncio.base import AsyncAbstractInstrumentedModule


class RedisAsyncioInstrumentation(AsyncAbstractInstrumentedModule):
    name = "redis"

    instrument_list = [
        ("redis.asyncio.client", "Redis.execute_command"),
        ("redis.asyncio.client", "PubSub.execute_command"),
    ]

    async def call(self, module, method, wrapped, instance, args, kwargs):
        if len(args) > 0:
            wrapped_name = args[0]
            if isinstance(wrapped_name, bytes):
                wrapped_name = wrapped_name.decode()
        else:
            wrapped_name = self.get_wrapped_name(wrapped, instance, method)

        async with async_capture_span(
            wrapped_name, span_type="db", span_subtype="redis", span_action="query", leaf=True
        ) as span:
            if span.context is not None:
                span.context["destination"] = _get_destination_info(instance)

            return await wrapped(*args, **kwargs)


class RedisPipelineInstrumentation(AsyncAbstractInstrumentedModule):
    name = "redis"

    instrument_list = [("redis.asyncio.client", "Pipeline.execute")]

    async def call(self, module, method, wrapped, instance, args, kwargs):
        wrapped_name = self.get_wrapped_name(wrapped, instance, method)

        async with async_capture_span(
            wrapped_name, span_type="db", span_subtype="redis", span_action="query", leaf=True
        ) as span:
            if span.context is not None:
                span.context["destination"] = _get_destination_info(instance)

            return await wrapped(*args, **kwargs)


def _get_destination_info(connection):
    destination_info = {"service": {"name": "", "resource": "redis", "type": ""}}
    if connection.connection_pool:
        destination_info["port"] = connection.connection_pool.connection_kwargs.get("port")
        destination_info["address"] = connection.connection_pool.connection_kwargs.get("host")

    return destination_info
