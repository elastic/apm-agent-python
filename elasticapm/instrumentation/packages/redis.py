from __future__ import absolute_import

from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.traces import capture_span


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
    instrument_list_3 = [("redis.client", "Redis.execute_command")]
    instrument_list = [("redis.client", "Redis.execute_command"), ("redis.client", "StrictRedis.execute_command")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        if len(args) > 0:
            wrapped_name = str(args[0])
        else:
            wrapped_name = self.get_wrapped_name(wrapped, instance, method)

        with capture_span(wrapped_name, "cache.redis", leaf=True):
            return wrapped(*args, **kwargs)


class RedisPipelineInstrumentation(Redis3CheckMixin, AbstractInstrumentedModule):
    name = "redis"

    # BasePipeline has been renamed to Pipeline in redis-py 3
    instrument_list_3 = [("redis.client", "Pipeline.execute")]
    instrument_list = [("redis.client", "BasePipeline.execute")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        wrapped_name = self.get_wrapped_name(wrapped, instance, method)
        with capture_span(wrapped_name, "cache.redis", leaf=True):
            return wrapped(*args, **kwargs)
