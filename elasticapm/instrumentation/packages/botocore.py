from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.traces import trace
from elasticapm.utils.compat import urlparse


class BotocoreInstrumentation(AbstractInstrumentedModule):
    name = 'botocore'

    instrument_list = [
        ('botocore.client', 'BaseClient._make_api_call'),
    ]

    def call(self, module, method, wrapped, instance, args, kwargs):
        if 'operation_name' in kwargs:
            operation_name = kwargs['operation_name']
        else:
            operation_name = args[0]

        target_endpoint = instance._endpoint.host
        parsed_url = urlparse.urlparse(target_endpoint)
        service, region, _ = parsed_url.hostname.split('.', 2)

        signature = '{}:{}'.format(service, operation_name)
        extra_data = {
            'service': service,
            'region': region,
            'operation': operation_name,
        }

        with trace(signature, 'ext.http.aws', extra_data, leaf=True):
            return wrapped(*args, **kwargs)
