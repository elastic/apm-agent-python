from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.traces import capture_span


class ZLibInstrumentation(AbstractInstrumentedModule):
    name = "zlib"
    instrument_list = [("zlib", "compress"), ("zlib", "decompress")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        wrapped_name = module + "." + method
        with capture_span(wrapped_name, "compression.zlib"):
            return wrapped(*args, **kwargs)
