from elasticapm.conf import constants
from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.traces import DroppedSpan, capture_span, get_transaction
from elasticapm.utils import default_ports
from elasticapm.utils.disttracing import TracingOptions


class Urllib3Instrumentation(AbstractInstrumentedModule):
    name = "urllib3"

    instrument_list = [
        ("urllib3.connectionpool", "HTTPConnectionPool.urlopen"),
        ("requests.packages.urllib3.connectionpool", "HTTPConnectionPool.urlopen"),
    ]

    def call(self, module, method, wrapped, instance, args, kwargs):
        if "method" in kwargs:
            method = kwargs["method"]
        else:
            method = args[0]

        headers = None
        if "headers" in kwargs:
            headers = kwargs["headers"]
            if headers is None:
                headers = {}
                kwargs["headers"] = headers

        host = instance.host

        if instance.port != default_ports.get(instance.scheme):
            host += ":" + str(instance.port)

        if "url" in kwargs:
            url = kwargs["url"]
        else:
            url = args[1]

        signature = method.upper() + " " + host

        url = instance.scheme + "://" + host + url
        transaction = get_transaction()

        with capture_span(signature, "ext.http.urllib3", {"url": url}, leaf=True) as span:
            # if urllib3 has been called in a leaf span, this span might be a DroppedSpan.
            leaf_span = span
            while isinstance(leaf_span, DroppedSpan):
                leaf_span = leaf_span.parent

            if headers is not None:
                # It's possible that there are only dropped spans, e.g. if we started dropping spans.
                # In this case, the transaction.id is used
                parent_id = leaf_span.id if leaf_span else transaction.id
                trace_parent = transaction.trace_parent.copy_from(
                    span_id=parent_id, trace_options=TracingOptions(recorded=True)
                )
                headers[constants.TRACEPARENT_HEADER_NAME] = trace_parent.to_ascii()
            return wrapped(*args, **kwargs)

    def mutate_unsampled_call_args(self, module, method, wrapped, instance, args, kwargs, transaction):
        # since we don't have a span, we set the span id to the transaction id
        trace_parent = transaction.trace_parent.copy_from(
            span_id=transaction.id, trace_options=TracingOptions(recorded=False)
        )
        if "headers" in kwargs:
            headers = kwargs["headers"]
            if headers is None:
                headers = {}
                kwargs["headers"] = headers
            headers[constants.TRACEPARENT_HEADER_NAME] = trace_parent.to_ascii()
        return args, kwargs
