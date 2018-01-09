import inspect

from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.traces import capture_span


class ElasticsearchInstrumentation(AbstractInstrumentedModule):
    name = 'elasticsearch'

    instrument_list = [
        ('elasticsearch.transport', 'Transport.perform_request'),
        ('elasticsearch5.transport', 'Transport.perform_request'),
    ]

    def call(self, module, method, wrapped, instance, args, kwargs):
        try:
            curr_frame = inspect.currentframe()
            caller = inspect.currentframe().f_back.f_back.f_back
            function_name = caller.f_code.co_name
        except Exception:
            function_name = ''
        http_method = args[0]
        path = args[1]
        extra = {
            'db': {
                'type': 'elasticsearch',
            }
        }

        signature = '{} {}'.format(http_method, function_name or path)

        with capture_span(signature, 'db.elasticsearch', extra=extra, leaf=True):
            return wrapped(*args, **kwargs)
