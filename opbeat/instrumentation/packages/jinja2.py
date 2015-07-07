from opbeat.instrumentation.packages.base import AbstractInstrumentedModule


class Jinja2Instrumentation(AbstractInstrumentedModule):
    name = 'pylibmc'

    instrument_list = [
        ("jinja2", "Template.render"),
    ]

    def call(self, module, method, wrapped, instance, args, kwargs):
        signature = instance.name or instance.filename
        with self.client.capture_trace(signature, "template.jinja2"):
            return wrapped(*args, **kwargs)

