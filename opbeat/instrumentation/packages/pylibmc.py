from opbeat.instrumentation.packages.base import AbstractInstrumentedModule


class PyLibMcInstrumentation(AbstractInstrumentedModule):
    name = 'pylibmc'

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

    def call(self, wrapped, instance, args, kwargs):
        wrapped_name = instance.__class__.__name__ + "." + wrapped.__name__
        with self.client.capture_trace(wrapped_name, "cache.memcached"):
            return wrapped(*args, **kwargs)
