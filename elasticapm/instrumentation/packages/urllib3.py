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
from elasticapm.utils import default_ports
from elasticapm.utils.disttracing import TracingOptions


class Urllib3Instrumentation(AbstractInstrumentedModule):
    name = "urllib3"

    instrument_list = [
        ("urllib3.connectionpool", "HTTPConnectionPool.urlopen"),
        # packages that vendor or vendored urllib3 in the past
        ("requests.packages.urllib3.connectionpool", "HTTPConnectionPool.urlopen"),
        ("botocore.vendored.requests.packages.urllib3.connectionpool", "HTTPConnectionPool.urlopen"),
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

        # TODO: reconstruct URL more faithfully, e.g. include port
        url = instance.scheme + "://" + host + url
        transaction = execution_context.get_transaction()

        with capture_span(
            signature, span_type="external", span_subtype="http", extra={"http": {"url": url}}, leaf=True
        ) as span:
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
                headers[constants.TRACEPARENT_HEADER_NAME] = trace_parent.to_string()
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
            headers[constants.TRACEPARENT_HEADER_NAME] = trace_parent.to_string()
        return args, kwargs
