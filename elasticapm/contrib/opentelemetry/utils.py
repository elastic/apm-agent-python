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


from opentelemetry.trace import SpanKind
from opentelemetry.trace.span import SpanContext

import elasticapm.conf.constants as constants
from elasticapm.utils.disttracing import TraceParent, TracingOptions


def get_traceparent(otel_spancontext: SpanContext) -> TraceParent:
    """
    Create an elastic TraceParent object from an opentelemetry SpanContext
    """
    trace_id = None
    span_id = None
    is_sampled = False
    if otel_spancontext and otel_spancontext.is_valid:
        trace_id = otel_spancontext.trace_id
        span_id = otel_spancontext.span_id
        is_sampled = otel_spancontext.trace_flags.sampled
        tracestate = otel_spancontext.trace_state
    if trace_id:
        traceparent = TraceParent(
            constants.TRACE_CONTEXT_VERSION,
            "%032x" % trace_id,
            "%016x" % span_id,
            TracingOptions(recorded=is_sampled),
            tracestate=tracestate.to_header(),
        )
        return traceparent
    else:
        return None


def get_span_kind(kind: SpanKind) -> str:
    """
    Converts a SpanKind to the string representation
    """
    if kind == SpanKind.CLIENT:
        return "CLIENT"
    elif kind == SpanKind.CONSUMER:
        return "CONSUMER"
    elif kind == SpanKind.INTERNAL:
        return "INTERNAL"
    elif kind == SpanKind.PRODUCER:
        return "PRODUCER"
    elif kind == SpanKind.SERVER:
        return "SERVER"
    else:
        return "INTERNAL"
