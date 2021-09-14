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

from __future__ import absolute_import

import re

import elasticapm
from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.traces import DroppedSpan, execution_context
from elasticapm.utils.logging import get_logger

logger = get_logger("elasticapm.instrument")

should_capture_body_re = re.compile("/(_search|_msearch|_count|_async_search|_sql|_eql)(/|$)")


class ElasticsearchConnectionInstrumentation(AbstractInstrumentedModule):
    name = "elasticsearch_connection"

    instrument_list = [
        ("elasticsearch.connection.http_urllib3", "Urllib3HttpConnection.perform_request"),
        ("elasticsearch.connection.http_requests", "RequestsHttpConnection.perform_request"),
    ]

    def call(self, module, method, wrapped, instance, args, kwargs):
        span = execution_context.get_span()
        if isinstance(span, DroppedSpan):
            return wrapped(*args, **kwargs)

        self._update_context_by_request_data(span.context, instance, args, kwargs)

        status_code, headers, raw_data = wrapped(*args, **kwargs)

        span.context["http"] = {"status_code": status_code}

        return status_code, headers, raw_data

    def _update_context_by_request_data(self, context, instance, args, kwargs):
        args_len = len(args)
        url = args[1] if args_len > 1 else kwargs.get("url")
        params = args[2] if args_len > 2 else kwargs.get("params")
        body_serialized = args[3] if args_len > 3 else kwargs.get("body")

        should_capture_body = bool(should_capture_body_re.search(url))

        context["db"] = {"type": "elasticsearch"}
        if should_capture_body:
            query = []
            # using both q AND body is allowed in some API endpoints / ES versions,
            # but not in others. We simply capture both if they are there so the
            # user can see it.
            if params and "q" in params:
                # 'q' is already encoded to a byte string at this point
                # we assume utf8, which is the default
                query.append("q=" + params["q"].decode("utf-8", errors="replace"))
            if body_serialized:
                if isinstance(body_serialized, bytes):
                    query.append(body_serialized.decode("utf-8", errors="replace"))
                else:
                    query.append(body_serialized)
            if query:
                context["db"]["statement"] = "\n\n".join(query)

        context["destination"] = {
            "address": instance.host,
            "service": {"name": "elasticsearch", "resource": "elasticsearch", "type": "db"},
        }


class ElasticsearchTransportInstrumentation(AbstractInstrumentedModule):
    name = "elasticsearch_connection"

    instrument_list = [
        ("elasticsearch.transport", "Transport.perform_request"),
    ]

    def call(self, module, method, wrapped, instance, args, kwargs):
        with elasticapm.capture_span(
            self._get_signature(args, kwargs),
            span_type="db",
            span_subtype="elasticsearch",
            span_action="query",
            extra={},
            skip_frames=2,
            leaf=True,
        ) as span:
            result_data = wrapped(*args, **kwargs)

            try:
                span.context["db"]["rows_affected"] = result_data["hits"]["total"]["value"]
            except (KeyError, TypeError):
                pass

            return result_data

    def _get_signature(self, args, kwargs):
        args_len = len(args)
        http_method = args[0] if args_len else kwargs.get("method")
        http_path = args[1] if args_len > 1 else kwargs.get("url")

        return "ES %s %s" % (http_method, http_path)
