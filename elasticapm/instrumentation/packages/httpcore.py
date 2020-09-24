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
from elasticapm.utils import default_ports, url_to_destination
from elasticapm.utils.disttracing import TracingOptions


class HTTPCoreInstrumentation(AbstractInstrumentedModule):
    name = "httpcore"

    instrument_list = [
        ("httpcore._sync.connection", "SyncHTTPConnection.request"),
    ]

    def call(self, module, method, wrapped, instance, args, kwargs):
        if "method" in kwargs:
            method = kwargs["method"].decode("utf-8")
        else:
            method = args[0].decode("utf-8")

        # URL is a tuple of (scheme, host, port, path), we want path
        if "url" in kwargs:
            url = kwargs["url"][3].decode("utf-8")
        else:
            url = args[1][3].decode("utf-8")

        headers = None
        if "headers" in kwargs:
            headers = kwargs["headers"]
            if headers is None:
                headers = []
                kwargs["headers"] = headers

        scheme, host, port = instance.origin
        scheme = scheme.decode("utf-8")
        host = host.decode("utf-8")

        if port != default_ports.get(scheme):
            host += ":" + str(port)

        signature = "%s %s" % (method.upper(), host)

        url = "%s://%s%s" % (scheme, host, url)
        destination = url_to_destination(url)

        transaction = execution_context.get_transaction()

        with capture_span(
            signature,
            span_type="external",
            span_subtype="http",
            extra={"http": {"url": url}, "destination": destination},
            leaf=True,
        ) as span:
            # if httpcore has been called in a leaf span, this span might be a DroppedSpan.
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
                self._set_disttracing_headers(headers, trace_parent, transaction)
            response = wrapped(*args, **kwargs)
            if len(response) > 4:
                # httpcore < 0.11.0
                # response = (http_version, status_code, reason_phrase, headers, stream)
                status_code = response[1]
            else:
                # httpcore >= 0.11.0
                # response = (status_code, headers, stream, ext)
                status_code = response[0]
            if status_code:
                if span.context:
                    span.context["http"]["status_code"] = status_code
                span.set_success() if status_code < 400 else span.set_failure()
            return response

    def mutate_unsampled_call_args(self, module, method, wrapped, instance, args, kwargs, transaction):
        # since we don't have a span, we set the span id to the transaction id
        trace_parent = transaction.trace_parent.copy_from(
            span_id=transaction.id, trace_options=TracingOptions(recorded=False)
        )
        if "headers" in kwargs:
            headers = kwargs["headers"]
            if headers is None:
                headers = []
                kwargs["headers"] = headers
            self._set_disttracing_headers(headers, trace_parent, transaction)
        return args, kwargs

    def _set_disttracing_headers(self, headers, trace_parent, transaction):
        trace_parent_str = trace_parent.to_string()
        headers.append((bytes(constants.TRACEPARENT_HEADER_NAME, "utf-8"), bytes(trace_parent_str, "utf-8")))
        if transaction.tracer.config.use_elastic_traceparent_header:
            headers.append((bytes(constants.TRACEPARENT_LEGACY_HEADER_NAME, "utf-8"), bytes(trace_parent_str, "utf-8")))
        if trace_parent.tracestate:
            headers.append((bytes(constants.TRACESTATE_HEADER_NAME, "utf-8"), bytes(trace_parent.tracestate, "utf-8")))
