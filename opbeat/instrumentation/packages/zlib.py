from opbeat.instrumentation.packages.base import AbstractInstrumentedModule


class ZLibInstrumentation(AbstractInstrumentedModule):
    name = 'zlib'
    instrument_list = [
        ('zlib', 'compress'),
        ('zlib', 'decompress'),
    ]

    def call(self, module, method, wrapped, instance, args, kwargs):
        wrapped_name = module + "." + method
        with self.client.capture_trace(wrapped_name, "compression.zlib"):
            return wrapped(*args, **kwargs)
