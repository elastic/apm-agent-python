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

from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.traces import capture_span, execution_context


class Redis3CheckMixin(object):
    instrument_list_3 = []
    instrument_list = []

    def get_instrument_list(self):
        try:
            from redis import VERSION

            if VERSION[0] >= 3:
                return self.instrument_list_3
            return self.instrument_list
        except ImportError:
            return self.instrument_list


class RedisInstrumentation(Redis3CheckMixin, AbstractInstrumentedModule):
    name = "redis"

    # no need to instrument StrictRedis in redis-py >= 3.0
    instrument_list_3 = [("redis.client", "Redis.execute_command"), ("redis.client", "PubSub.execute_command")]
    instrument_list = [("redis.client", "Redis.execute_command"), ("redis.client", "StrictRedis.execute_command")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        if len(args) > 0:
            wrapped_name = str(args[0])
        else:
            wrapped_name = self.get_wrapped_name(wrapped, instance, method)

        with capture_span(wrapped_name, span_type="db", span_subtype="redis", span_action="query", leaf=True):
            return wrapped(*args, **kwargs)


class RedisPipelineInstrumentation(Redis3CheckMixin, AbstractInstrumentedModule):
    name = "redis"

    # BasePipeline has been renamed to Pipeline in redis-py 3
    instrument_list_3 = [("redis.client", "Pipeline.execute")]
    instrument_list = [("redis.client", "BasePipeline.execute")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        wrapped_name = self.get_wrapped_name(wrapped, instance, method)
        with capture_span(wrapped_name, span_type="db", span_subtype="redis", span_action="query", leaf=True):
            return wrapped(*args, **kwargs)


class RedisConnectionInstrumentation(AbstractInstrumentedModule):
    name = "redis"

    instrument_list = (("redis.connection", "Connection.send_packed_command"),)

    def call(self, module, method, wrapped, instance, args, kwargs):
        span = execution_context.get_span()
        db_context = None
        if args and len(args) > 1:
            func_name = args[0].decode("utf-8") if isinstance(args[0], bytes) else args[0]
            db_context = {"type": "query", "statement": "{} {}".format(func_name, args[1])}
        if span and span.subtype == self.name:
            span.context["destination"] = get_destination_info(instance)
            if db_context:
                span.context["db"] = db_context
        return wrapped(*args, **kwargs)


def get_destination_info(connection):
    destination_info = {}
    if hasattr(connection, "port"):
        destination_info["port"] = int(connection.port)
        destination_info["address"] = connection.host
    elif hasattr(connection, "path"):
        destination_info["port"] = None
        destination_info["address"] = "unix://" + connection.path
    return destination_info
