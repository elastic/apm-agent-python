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

import pytest
from opentelemetry.trace import SpanKind

import elasticapm.contrib.opentelemetry.context as context
from elasticapm.conf import constants
from elasticapm.contrib.opentelemetry.trace import Tracer
from elasticapm.traces import execution_context


@pytest.fixture
def tracer(elasticapm_client) -> Tracer:
    yield Tracer("test", elasticapm_client=elasticapm_client)


def test_root_transaction(tracer: Tracer):
    with tracer.start_as_current_span("test"):
        pass

    client = tracer.client
    transaction = client.events[constants.TRANSACTION][0]
    assert transaction["type"] == "unknown"
    assert transaction["name"] == "test"
    assert transaction["result"] == "OK"


def test_ot_span(tracer: Tracer):
    with tracer.start_as_current_span("test") as otel_transaction_span:
        with tracer.start_as_current_span("testspan", kind=SpanKind.CONSUMER) as otel_span:
            with tracer.start_as_current_span("testspan2") as otel_span2:
                pass
    client = tracer.client
    transaction = client.events[constants.TRANSACTION][0]
    span1 = client.events[constants.SPAN][1]
    span2 = client.events[constants.SPAN][0]
    assert span1["transaction_id"] == span1["parent_id"] == transaction["id"]
    assert span1["name"] == "testspan"

    assert span2["transaction_id"] == transaction["id"]
    assert span2["parent_id"] == span1["id"]
    assert span2["name"] == "testspan2"


# FIXME add a test for creating a span without attaching it
