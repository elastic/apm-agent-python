from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.traces import capture_span
from elasticapm.utils.compat import urlparse


class BotocoreInstrumentation(AbstractInstrumentedModule):
    name = "botocore"

    instrument_list = [("botocore.client", "BaseClient._make_api_call")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        if "operation_name" in kwargs:
            operation_name = kwargs["operation_name"]
        else:
            operation_name = args[0]

        target_endpoint = instance._endpoint.host
        parsed_url = urlparse.urlparse(target_endpoint)
        if "." in parsed_url.hostname:
            service = parsed_url.hostname.split(".", 2)[0]
        else:
            service = parsed_url.hostname

        signature = "{}:{}".format(service, operation_name)

        with capture_span(signature, "ext.http.aws", leaf=True):
            return wrapped(*args, **kwargs)
