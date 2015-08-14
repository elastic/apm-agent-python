from opbeat.instrumentation.packages.base import AbstractInstrumentedModule
from opbeat.traces import trace


class CelerySendTaskInstrumentation(AbstractInstrumentedModule):
    name = 'celery'

    instrument_list = [
        ("celery", "Celery.send_task"),
    ]

    def call(self, module, method, wrapped, instance, args, kwargs):
        wrapped_name = self.get_wrapped_name(wrapped, instance, method)
        with trace(wrapped_name, "queue.celery"):
            return wrapped(*args, **kwargs)


class CeleryApplyAsyncInstrumentation(AbstractInstrumentedModule):
    name = 'celery'

    instrument_list = [
        ("celery", "Task.apply_async"),
    ]

    def call(self, module, method, wrapped, instance, args, kwargs):
        wrapped_name = self.get_wrapped_name(wrapped, instance, method)
        if instance and hasattr(instance, "name"):
            wrapped_name += " " + instance.name
            
        with trace(wrapped_name, "queue.celery"):
            return wrapped(*args, **kwargs)
