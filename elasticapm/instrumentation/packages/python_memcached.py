from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.traces import capture_span


class PythonMemcachedInstrumentation(AbstractInstrumentedModule):
    name = "python_memcached"

    method_list = [
        "add",
        "append",
        "cas",
        "decr",
        "delete",
        "delete_multi",
        "disconnect_all",
        "flush_all",
        "get",
        "get_multi",
        "get_slabs",
        "get_stats",
        "gets",
        "incr",
        "prepend",
        "replace",
        "set",
        "set_multi",
        "touch",
    ]
    # Took out 'set_servers', 'reset_cas', 'debuglog', 'check_key' and
    # 'forget_dead_hosts' because they involve no communication.

    def get_instrument_list(self):
        return [("memcache", "Client." + method) for method in self.method_list]

    def call(self, module, method, wrapped, instance, args, kwargs):
        name = self.get_wrapped_name(wrapped, instance, method)

        with capture_span(name, "cache.memcached"):
            return wrapped(*args, **kwargs)
