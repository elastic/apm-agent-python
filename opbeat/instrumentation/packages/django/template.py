from opbeat.instrumentation.packages.base import AbstractInstrumentedModule


class DjangoTemplateInstrumentation(AbstractInstrumentedModule):
    name = 'django_template'

    instrument_list = [
        ("django.template", "Template._render"),
    ]

    def call(self, wrapped, instance, args, kwargs):
        with self.client.capture_trace(instance.name, "template.django"):
            return wrapped(*args, **kwargs)


