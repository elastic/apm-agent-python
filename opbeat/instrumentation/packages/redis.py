from importlib import import_module
from opbeat.instrumentation.packages.base import AbstractInstrumentedModule


class RedisInstrumentation(AbstractInstrumentedModule):
    name = 'redis'

    def get_instrument_list(self):
        instrument_list = []
        redis = import_module("redis")

        all_methods = self.get_public_methods(redis.StrictRedis)
        idx = all_methods.index(("redis.client", "StrictRedis.parse_response"))
        del all_methods[idx]

        instrument_list.extend(all_methods)

        all_methods = self.get_public_methods(redis.Redis)
        idx = all_methods.index(("redis.client", "Redis.parse_response"))
        del all_methods[idx]

        instrument_list.extend(all_methods)

        instrument_list.extend([
            ("redis.client", "BasePipeline.execute"),
            ("redis.client", "BasePipeline.watch"),
            ("redis.client", "BasePipeline.unwatch"),
        ])

        instrument_list.append(("redis.client", "Script.__call__"))
        return instrument_list

    def call(self, wrapped, instance, args, kwargs):
        wrapped_name = instance.__class__.__name__ + "." + wrapped.__name__
        with self.client.capture_trace(wrapped_name, "cache.redis"):
            return wrapped(*args, **kwargs)
