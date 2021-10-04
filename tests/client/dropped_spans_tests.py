#  BSD 3-Clause License
#
#  Copyright (c) 2021, Elasticsearch BV
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

import elasticapm
from elasticapm.conf import constants


@pytest.mark.parametrize("elasticapm_client", [{"transaction_max_spans": 5}], indirect=True)
def test_transaction_max_spans(elasticapm_client):
    elasticapm_client.begin_transaction("test_type")
    for i in range(5):
        with elasticapm.capture_span("nodrop"):
            pass
    for i in range(10):
        with elasticapm.capture_span("drop"):
            pass
    transaction_obj = elasticapm_client.end_transaction("test")

    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.events[constants.SPAN]
    assert all(span["transaction_id"] == transaction["id"] for span in spans)

    assert transaction_obj.dropped_spans == 10
    assert len(spans) == 5
    for span in spans:
        assert span["name"] == "nodrop"
    assert transaction["span_count"] == {"dropped": 10, "started": 5}


@pytest.mark.parametrize("elasticapm_client", [{"transaction_max_spans": 3}], indirect=True)
def test_transaction_max_span_nested(elasticapm_client):
    elasticapm_client.begin_transaction("test_type")
    with elasticapm.capture_span("1"):
        with elasticapm.capture_span("2"):
            with elasticapm.capture_span("3"):
                with elasticapm.capture_span("4"):
                    with elasticapm.capture_span("5"):
                        pass
                with elasticapm.capture_span("6"):
                    pass
            with elasticapm.capture_span("7"):
                pass
        with elasticapm.capture_span("8"):
            pass
    with elasticapm.capture_span("9"):
        pass
    transaction_obj = elasticapm_client.end_transaction("test")

    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.events[constants.SPAN]

    assert transaction_obj.dropped_spans == 6
    assert len(spans) == 3
    for span in spans:
        assert span["name"] in ("1", "2", "3")
    assert transaction["span_count"] == {"dropped": 6, "started": 3}


@pytest.mark.parametrize("elasticapm_client", [{"transaction_max_spans": 1}], indirect=True)
def test_transaction_max_span_dropped_statistics(elasticapm_client):
    elasticapm_client.begin_transaction("test_type")
    with elasticapm.capture_span("not_dropped"):
        pass
    for i in range(10):
        resource = str(i % 2)
        with elasticapm.capture_span(
            span_type="x", span_subtype="y", extra={"destination": {"service": {"resource": resource}}}, duration=100
        ):
            pass
    elasticapm_client.end_transaction()
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.events[constants.SPAN]

    assert len(spans) == 1
    for entry in transaction["dropped_spans_stats"]:
        assert entry["duration"]["count"] == 5
        assert entry["duration"]["sum"]["us"] == 500000000


@pytest.mark.parametrize("elasticapm_client", [{"transaction_max_spans": 1, "server_version": (7, 15)}], indirect=True)
def test_transaction_max_span_dropped_statistics_not_collected_for_incompatible_server(elasticapm_client):
    elasticapm_client.begin_transaction("test_type")
    with elasticapm.capture_span("not_dropped"):
        pass
    with elasticapm.capture_span(
        span_type="x", span_subtype="x", extra={"destination": {"service": {"resource": "y"}}}, duration=100
    ):
        pass
    elasticapm_client.end_transaction()
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.events[constants.SPAN]
    assert len(spans) == 1
    assert "dropped_spans_stats" not in transaction
