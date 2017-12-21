from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.traces import capture_span


class RedisInstrumentation(AbstractInstrumentedModule):
    name = 'redis'

    instrument_list = [
        ("redis.client", "Redis.execute_command"),
        ("redis.client", "StrictRedis.execute_command"),
    ]

    def call(self, module, method, wrapped, instance, args, kwargs):
        if len(args) > 0:
            wrapped_name = str(args[0])
        else:
            wrapped_name = self.get_wrapped_name(wrapped, instance, method)

        with capture_span(wrapped_name, "cache.redis", leaf=True):
            return wrapped(*args, **kwargs)


class RedisPipelineInstrumentation(AbstractInstrumentedModule):
    name = 'redis'

    instrument_list = [
        ("redis.client", "BasePipeline.execute"),
    ]

    def call(self, module, method, wrapped, instance, args, kwargs):
        wrapped_name = self.get_wrapped_name(wrapped, instance, method)
        with capture_span(wrapped_name, "cache.redis", leaf=True):
            return wrapped(*args, **kwargs)
