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
from elasticapm.conf.constants import SPAN, TRANSACTION


@pytest.mark.parametrize(
    "elasticapm_client",
    [
        {
            "span_compression_enabled": True,
            "span_compression_same_kind_max_duration": "5ms",
            "span_compression_exact_match_max_duration": "5ms",
        }
    ],
    indirect=True,
)
def test_exact_match(elasticapm_client):
    transaction = elasticapm_client.begin_transaction("test")
    with elasticapm.capture_span(
        "test",
        span_type="a",
        span_subtype="b",
        span_action="c",
        leaf=True,
        duration=0.002,
        extra={"destination": {"service": {"resource": "x"}}},
    ) as span1:
        assert span1.is_compression_eligible()
    with elasticapm.capture_span(
        "test",
        span_type="a",
        span_subtype="b",
        span_action="c",
        leaf=True,
        duration=0.003,
        extra={"destination": {"service": {"resource": "x"}}},
    ) as span2:
        pass
    assert span2.is_compression_eligible()
    assert span1.is_exact_match(span2)
    elasticapm_client.end_transaction("test")
    spans = elasticapm_client.events[SPAN]
    assert len(spans) == 1
    span = spans[0]
    assert "composite" in span
    assert span["composite"]["count"] == 2
    assert span["composite"]["sum"] == 5
    assert span["composite"]["compression_strategy"] == "exact_match"


@pytest.mark.parametrize(
    "elasticapm_client",
    [
        {
            "span_compression_enabled": True,
            "span_compression_same_kind_max_duration": "5ms",
            "span_compression_exact_match_max_duration": "5ms",
        }
    ],
    indirect=True,
)
def test_same_kind(elasticapm_client):
    transaction = elasticapm_client.begin_transaction("test")
    with elasticapm.capture_span(
        "test1",
        span_type="a",
        span_subtype="b",
        span_action="c",
        leaf=True,
        duration=0.002,
        extra={"destination": {"service": {"resource": "x"}}},
    ) as span1:
        assert span1.is_compression_eligible()
    with elasticapm.capture_span(
        "test2",
        span_type="a",
        span_subtype="b",
        span_action="c",
        leaf=True,
        duration=0.003,
        extra={"destination": {"service": {"resource": "x"}}},
    ) as span2:
        pass
    assert span2.is_compression_eligible()
    assert not span1.is_exact_match(span2)
    assert span1.is_same_kind(span2)
    elasticapm_client.end_transaction("test")
    spans = elasticapm_client.events[SPAN]
    assert len(spans) == 1
    span = spans[0]

    assert span["name"] == "Calls to x"
    assert "composite" in span
    assert span["composite"]["count"] == 2
    assert span["composite"]["sum"] == 5
    assert span["composite"]["compression_strategy"] == "same_kind"


@pytest.mark.parametrize(
    "elasticapm_client",
    [
        {
            "span_compression_enabled": True,
            "span_compression_same_kind_max_duration": "5ms",
            "span_compression_exact_match_max_duration": "5ms",
        }
    ],
    indirect=True,
)
def test_exact_match_after_same_kind(elasticapm_client):
    # if a span that is an exact match is attempted to be compressed with a same_kind composite, it stays same_kind
    transaction = elasticapm_client.begin_transaction("test")
    with elasticapm.capture_span(
        "test1",
        span_type="a",
        span_subtype="b",
        span_action="c",
        leaf=True,
        duration=0.002,
        extra={"destination": {"service": {"resource": "x"}}},
    ) as span1:
        assert span1.is_compression_eligible()
    with elasticapm.capture_span(
        "test2",
        span_type="a",
        span_subtype="b",
        span_action="c",
        leaf=True,
        duration=0.003,
        extra={"destination": {"service": {"resource": "x"}}},
    ) as span2:
        pass
    assert span2.is_compression_eligible()
    assert not span1.is_exact_match(span2)
    assert span1.is_same_kind(span2)
    with elasticapm.capture_span(
        "test1",
        span_type="a",
        span_subtype="b",
        span_action="c",
        leaf=True,
        duration=0.002,
        extra={"destination": {"service": {"resource": "x"}}},
    ) as span3:
        assert span3.is_compression_eligible()
    elasticapm_client.end_transaction("test")
    spans = elasticapm_client.events[SPAN]
    assert len(spans) == 1
    span = spans[0]
    assert span["composite"]["compression_strategy"] == "same_kind"
    assert span["composite"]["count"] == 3


@pytest.mark.parametrize(
    "elasticapm_client",
    [
        {
            "span_compression_enabled": True,
            "span_compression_same_kind_max_duration": "5ms",
            "span_compression_exact_match_max_duration": "5ms",
        }
    ],
    indirect=True,
)
def test_nested_spans(elasticapm_client):
    transaction = elasticapm_client.begin_transaction("test")
    with elasticapm.capture_span("test", "x.y.z") as span1:
        with elasticapm.capture_span(
            "test1",
            span_type="a",
            span_subtype="b",
            span_action="c",
            leaf=True,
            duration=0.002,
            extra={"destination": {"service": {"resource": "x"}}},
        ) as span2:
            pass
        with elasticapm.capture_span(
            "test2",
            span_type="a",
            span_subtype="b",
            span_action="c",
            leaf=True,
            duration=0.002,
            extra={"destination": {"service": {"resource": "x"}}},
        ) as span3:
            pass
        assert span1.compression_buffer is span2
        assert span2.composite
    # assert transaction.compression_buffer is span1
    # assert not span1.compression_buffer
    elasticapm_client.end_transaction("test")
    spans = elasticapm_client.events[SPAN]
    assert len(spans) == 2


@pytest.mark.parametrize(
    "elasticapm_client",
    [
        {
            "span_compression_enabled": True,
            "span_compression_same_kind_max_duration": "5ms",
            "span_compression_exact_match_max_duration": "5ms",
        }
    ],
    indirect=True,
)
def test_buffer_is_reported_if_next_child_ineligible(elasticapm_client):
    transaction = elasticapm_client.begin_transaction("test")
    with elasticapm.capture_span("test", "x.y.z") as span1:
        with elasticapm.capture_span(
            "test",
            "x.y.z",
            leaf=True,
            duration=0.002,
            extra={"destination": {"service": {"resource": "x"}}},
        ) as span2:
            pass
        assert span1.compression_buffer is span2
        with elasticapm.capture_span("test", "x.y.z") as span3:
            pass
        assert span1.compression_buffer is None
    elasticapm_client.end_transaction("test")
    spans = elasticapm_client.events[SPAN]
    assert len(spans) == 3


@pytest.mark.parametrize(
    "elasticapm_client",
    [
        {
            "span_compression_enabled": True,
            "span_compression_same_kind_max_duration": "5ms",
            "span_compression_exact_match_max_duration": "5ms",
        }
    ],
    indirect=True,
)
def test_compressed_spans_not_counted(elasticapm_client):
    t = elasticapm_client.begin_transaction("test")
    assert t.config_span_compression_enabled
    assert t.config_span_compression_exact_match_max_duration.total_seconds() == 0.005
    assert t.config_span_compression_same_kind_max_duration.total_seconds() == 0.005
    with elasticapm.capture_span(
        "test1",
        span_type="a",
        span_subtype="b",
        span_action="c",
        leaf=True,
        duration=0.002,
        extra={"destination": {"service": {"resource": "x"}}},
    ) as span1:
        pass
    with elasticapm.capture_span(
        "test2",
        span_type="a",
        span_subtype="b",
        span_action="c",
        leaf=True,
        duration=0.003,
        extra={"destination": {"service": {"resource": "x"}}},
    ) as span2:
        pass
    elasticapm_client.end_transaction("test")
    assert len(elasticapm_client.events[TRANSACTION]) == 1
    transaction = elasticapm_client.events[TRANSACTION][0]
    spans = elasticapm_client.events[SPAN]
    assert len(spans) == 1
    assert transaction["span_count"]["started"] == 1
    assert transaction["span_count"]["dropped"] == 0


@pytest.mark.parametrize(
    "elasticapm_client",
    [
        {
            "span_compression_enabled": False,
            "span_compression_same_kind_max_duration": "5ms",
            "span_compression_exact_match_max_duration": "5ms",
        }
    ],
    indirect=True,
)
def test_span_compression_disabled(elasticapm_client):
    transaction = elasticapm_client.begin_transaction("test")
    with elasticapm.capture_span(
        "test",
        span_type="a",
        span_subtype="b",
        span_action="c",
        leaf=True,
        duration=2,
        extra={"destination": {"service": {"resource": "x"}}},
    ) as span1:
        assert not span1.is_compression_eligible()
    with elasticapm.capture_span(
        "test",
        span_type="a",
        span_subtype="b",
        span_action="c",
        leaf=True,
        duration=3,
        extra={"destination": {"service": {"resource": "x"}}},
    ) as span2:
        assert not span2.is_compression_eligible()
    elasticapm_client.end_transaction("test")
    spans = elasticapm_client.events[SPAN]
    assert len(spans) == 2
    span = spans[0]
    assert "composite" not in span
