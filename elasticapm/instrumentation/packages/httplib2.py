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
from elasticapm.utils import get_host_from_url, sanitize_url, url_to_destination
from elasticapm.utils.disttracing import TracingOptions


class Httplib2Instrumentation(AbstractInstrumentedModule):
    name = "httplib2"

    instrument_list = [("httplib2", "Http.request")]

    # https://httplib2.readthedocs.io/en/latest/libhttplib2.html#httplib2.Http.request
    args_list = ("url", "method", "body", "headers")

    def _ensure_headers_in_kwargs(self, args, kwargs):
        # strip out trailing None positional arguments
        if len(args) > 2:
            for _ in range(2, len(self.args_list)):
                if args[-1] is not None:
                    break
                args = args[:-1]

        # grab args passed in as positional
        params = dict(zip(self.args_list, args))

        # fall back to kwargs for args not supplied as positional
        for arg in self.args_list:
            if arg in params:
                continue
            if arg in kwargs:
                params[arg] = kwargs[arg]

        if "headers" not in params:
            kwargs["headers"] = params["headers"] = {}

        return args, kwargs, params

    def call(self, module, method, wrapped, instance, args, kwargs):
        args, kwargs, params = self._ensure_headers_in_kwargs(args, kwargs)

        signature = params.get("method", "GET").upper()
        signature += " " + get_host_from_url(params["url"])
        url = sanitize_url(params["url"])
        destination = url_to_destination(url)
        transaction = execution_context.get_transaction()
        with capture_span(
            signature,
            span_type="external",
            span_subtype="http",
            extra={"http": {"url": url}, "destination": destination},
            leaf=True,
        ) as span:
            # if httplib2 has been called in a leaf span, this span might be a DroppedSpan.
            leaf_span = span
            while isinstance(leaf_span, DroppedSpan):
                leaf_span = leaf_span.parent

            # It's possible that there are only dropped spans, e.g. if we started dropping spans.
            # In this case, the transaction.id is used
            parent_id = leaf_span.id if leaf_span else transaction.id
            trace_parent = transaction.trace_parent.copy_from(
                span_id=parent_id, trace_options=TracingOptions(recorded=True)
            )
            self._set_disttracing_headers(params["headers"], trace_parent, transaction)

            response, content = wrapped(*args, **kwargs)
            if span.context:
                span.context["http"]["status_code"] = response.status
            span.set_success() if response.status < 400 else span.set_failure()
            return response, content

    def mutate_unsampled_call_args(self, module, method, wrapped, instance, args, kwargs, transaction):
        # since we don't have a span, we set the span id to the transaction id
        trace_parent = transaction.trace_parent.copy_from(
            span_id=transaction.id, trace_options=TracingOptions(recorded=False)
        )
        args, kwargs, params = self._ensure_headers_in_kwargs(args, kwargs)
        self._set_disttracing_headers(params["headers"], trace_parent, transaction)
        return args, kwargs

    def _set_disttracing_headers(self, headers, trace_parent, transaction):
        trace_parent_str = trace_parent.to_string()
        headers[constants.TRACEPARENT_HEADER_NAME] = trace_parent_str
        if transaction.tracer.config.use_elastic_traceparent_header:
            headers[constants.TRACEPARENT_LEGACY_HEADER_NAME] = trace_parent_str
        if trace_parent.tracestate:
            headers[constants.TRACESTATE_HEADER_NAME] = trace_parent.tracestate
