from opbeat.instrumentation.packages.base import AbstractInstrumentedModule


class DjangoTemplateInstrumentation(AbstractInstrumentedModule):
    name = 'django_template'

    instrument_list = [
        ("django.template", "Template.render"),
    ]

    def call(self, wrapped, instance, args, kwargs):
        name = getattr(instance, 'name', None)

        if not name:
            name = '<template string>'
        with self.client.capture_trace(name, "template.django"):
            return wrapped(*args, **kwargs)
