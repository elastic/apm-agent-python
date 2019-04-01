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

import logging

from opentracing.ext import tags
from opentracing.span import Span as OTSpanBase
from opentracing.span import SpanContext as OTSpanContextBase

from elasticapm import traces
from elasticapm.utils import compat, get_url_dict

logger = logging.getLogger("elasticapm.contrib.opentracing")


class OTSpan(OTSpanBase):
    def __init__(self, tracer, context, elastic_apm_ref):
        super(OTSpan, self).__init__(tracer, context)
        self.elastic_apm_ref = elastic_apm_ref
        self.is_transaction = isinstance(elastic_apm_ref, traces.Transaction)
        if not context.span:
            context.span = self

    def log_kv(self, key_values, timestamp=None):
        if "python.exception.type" in key_values:
            agent = self.tracer._agent
            agent.capture_exception(
                exc_info=(
                    key_values["python.exception.type"],
                    key_values.get("python.exception.val"),
                    key_values.get("python.exception.tb"),
                )
            )
        else:
            logger.debug("Can't handle non-exception type opentracing logs")
        return self

    def set_operation_name(self, operation_name):
        self.elastic_apm_ref.name = operation_name
        return self

    def set_tag(self, key, value):
        if self.is_transaction:
            if key == "type":
                self.elastic_apm_ref.transaction_type = value
            elif key == "result":
                self.elastic_apm_ref.result = value
            elif key == tags.HTTP_STATUS_CODE:
                self.elastic_apm_ref.result = "HTTP {}xx".format(compat.text_type(value)[0])
                traces.set_context({"status_code": value}, "response")
            elif key == "user.id":
                traces.set_user_context(user_id=value)
            elif key == "user.username":
                traces.set_user_context(username=value)
            elif key == "user.email":
                traces.set_user_context(email=value)
            elif key == tags.HTTP_URL:
                traces.set_context({"url": get_url_dict(value)}, "request")
            elif key == tags.HTTP_METHOD:
                traces.set_context({"method": value}, "request")
            elif key == tags.COMPONENT:
                traces.set_context({"framework": {"name": value}}, "service")
            else:
                self.elastic_apm_ref.tag(**{key: value})
        else:
            if key.startswith("db."):
                span_context = self.elastic_apm_ref.context or {}
                if "db" not in span_context:
                    span_context["db"] = {}
                if key == tags.DATABASE_STATEMENT:
                    span_context["db"]["statement"] = value
                elif key == tags.DATABASE_USER:
                    span_context["db"]["user"] = value
                elif key == tags.DATABASE_TYPE:
                    span_context["db"]["type"] = value
                    self.elastic_apm_ref.type = "db." + value
                else:
                    self.elastic_apm_ref.tag(**{key: value})
                self.elastic_apm_ref.context = span_context
            elif key == tags.SPAN_KIND:
                self.elastic_apm_ref.type = value
            else:
                self.elastic_apm_ref.tag(**{key: value})
        return self

    def finish(self, finish_time=None):
        if self.is_transaction:
            self.tracer._agent.end_transaction()
        else:
            self.elastic_apm_ref.transaction.end_span()


class OTSpanContext(OTSpanContextBase):
    def __init__(self, trace_parent, span=None):
        self.trace_parent = trace_parent
        self.span = span
