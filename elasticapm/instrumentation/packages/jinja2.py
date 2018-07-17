from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.traces import capture_span


class Jinja2Instrumentation(AbstractInstrumentedModule):
    name = "jinja2"

    instrument_list = [("jinja2", "Template.render")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        signature = instance.name or instance.filename
        with capture_span(signature, "template.jinja2"):
            return wrapped(*args, **kwargs)
