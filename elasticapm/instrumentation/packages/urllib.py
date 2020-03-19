#  BSD 3-Clause License
#
#  Copyright (c) 2019, Elasticsearch BV
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  * Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


from elasticapm.conf import constants
from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.traces import DroppedSpan, capture_span, execution_context
from elasticapm.utils import compat, default_ports, sanitize_url, url_to_destination
from elasticapm.utils.disttracing import TracingOptions


# copied and adapted from urllib.request
def request_host(request):
    """Return request-host, as defined by RFC 2965.

    Variation from RFC: returned value is lowercased, for convenient
    comparison.

    """
    url = request.get_full_url()
    parse_result = compat.urlparse.urlparse(url)
    scheme, host, port = parse_result.scheme, parse_result.hostname, parse_result.port
    try:
        port = int(port)
    except (ValueError, TypeError):
        pass
    if host == "":
        host = request.get_header("Host", "")

    if port and port != default_ports.get(scheme):
        host = "%s:%s" % (host, port)
    return host


class UrllibInstrumentation(AbstractInstrumentedModule):
    name = "urllib"

    if compat.PY2:
        instrument_list = [("urllib2", "AbstractHTTPHandler.do_open")]
    else:
        instrument_list = [("urllib.request", "AbstractHTTPHandler.do_open")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        request_object = args[1] if len(args) > 1 else kwargs["req"]

        method = request_object.get_method()
        host = request_host(request_object)

        url = sanitize_url(request_object.get_full_url())
        destination = url_to_destination(url)
        signature = method.upper() + " " + host

        transaction = execution_context.get_transaction()

        with capture_span(
            signature,
            span_type="external",
            span_subtype="http",
            extra={"http": {"url": url}, "destination": destination},
            leaf=True,
        ) as span:
            # if urllib has been called in a leaf span, this span might be a DroppedSpan.
            leaf_span = span
            while isinstance(leaf_span, DroppedSpan):
                leaf_span = leaf_span.parent

            parent_id = leaf_span.id if leaf_span else transaction.id
            trace_parent = transaction.trace_parent.copy_from(
                span_id=parent_id, trace_options=TracingOptions(recorded=True)
            )
            self._set_disttracing_headers(request_object, trace_parent, transaction)
            return wrapped(*args, **kwargs)

    def mutate_unsampled_call_args(self, module, method, wrapped, instance, args, kwargs, transaction):
        request_object = args[1] if len(args) > 1 else kwargs["req"]
        # since we don't have a span, we set the span id to the transaction id
        trace_parent = transaction.trace_parent.copy_from(
            span_id=transaction.id, trace_options=TracingOptions(recorded=False)
        )

        self._set_disttracing_headers(request_object, trace_parent, transaction)
        return args, kwargs

    def _set_disttracing_headers(self, request_object, trace_parent, transaction):
        trace_parent_str = trace_parent.to_string()
        request_object.add_header(constants.TRACEPARENT_HEADER_NAME, trace_parent_str)
        if transaction.tracer.config.use_elastic_traceparent_header:
            request_object.add_header(constants.TRACEPARENT_LEGACY_HEADER_NAME, trace_parent_str)
        if trace_parent.tracestate:
            request_object.add_header(constants.TRACESTATE_HEADER_NAME, trace_parent.tracestate)
