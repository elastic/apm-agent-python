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
import elasticapm
from elasticapm.conf.constants import SPAN


def test_config_snapshotting_span_compression_exact_match(elasticapm_client):
    elasticapm_client.config.update(
        version="1",
        **{
            "span_compression_enabled": "true",
            "span_compression_exact_match_max_duration": "50ms",
            "span_compression_same_kind_max_duration": "10ms",
        }
    )
    elasticapm_client.begin_transaction("foo")
    elasticapm_client.config.update(
        version="2", **{"span_compression_enabled": "false", "span_compression_exact_match_max_duration": "20ms"}
    )
    with elasticapm.capture_span(
        "x",
        leaf=True,
        span_type="a",
        span_subtype="b",
        span_action="c",
        extra={"destination": {"service": {"resource": "x"}}},
        duration=0.025,
    ):
        pass
    with elasticapm.capture_span(
        "x",
        leaf=True,
        span_type="a",
        span_subtype="b",
        span_action="c",
        extra={"destination": {"service": {"resource": "x"}}},
        duration=0.025,
    ):
        pass
    elasticapm_client.end_transaction()
    spans = elasticapm_client.events[SPAN]
    assert len(spans) == 1
    assert spans[0]["composite"]["compression_strategy"] == "exact_match"


def test_config_snapshotting_span_compression_same_kind(elasticapm_client):
    elasticapm_client.config.update(
        version="1", **{"span_compression_enabled": "true", "span_compression_same_kind_max_duration": "50ms"}
    )
    elasticapm_client.begin_transaction("foo")
    elasticapm_client.config.update(
        version="2", **{"span_compression_enabled": "false", "span_compression_same_kind_max_duration": "20ms"}
    )
    with elasticapm.capture_span(
        "x",
        leaf=True,
        span_type="a",
        span_subtype="b",
        span_action="c",
        extra={"destination": {"service": {"resource": "x"}}},
        duration=0.025,
    ):
        pass
    with elasticapm.capture_span(
        "y",
        leaf=True,
        span_type="a",
        span_subtype="b",
        span_action="c",
        extra={"destination": {"service": {"resource": "x"}}},
        duration=0.025,
    ):
        pass
    elasticapm_client.end_transaction()
    spans = elasticapm_client.events[SPAN]
    assert len(spans) == 1
    assert spans[0]["composite"]["compression_strategy"] == "same_kind"


def test_config_snapshotting_span_compression_drop_exit_span(elasticapm_client):
    elasticapm_client.config.update(version="1", exit_span_min_duration="10ms")
    elasticapm_client.begin_transaction("foo")
    elasticapm_client.config.update(version="2", exit_span_min_duration="0ms")
    with elasticapm.capture_span(
        "x",
        leaf=True,
        span_type="a",
        span_subtype="b",
        span_action="c",
        extra={"destination": {"service": {"resource": "x"}}},
        duration=0.005,
    ):
        pass
    elasticapm_client.end_transaction()
    spans = elasticapm_client.events[SPAN]
    assert len(spans) == 0


def test_config_snapshotting_span_compression_max_spans(elasticapm_client):
    elasticapm_client.config.update(version="1", transaction_max_spans="1")
    elasticapm_client.begin_transaction("foo")
    elasticapm_client.config.update(version="2", transaction_max_spans="100")
    with elasticapm.capture_span("x", leaf=True, span_type="x", span_subtype="y", span_action="z"):
        pass
    with elasticapm.capture_span("x", leaf=True, span_type="a", span_subtype="b", span_action="c"):
        pass
    elasticapm_client.end_transaction()
    spans = elasticapm_client.events[SPAN]
    assert len(spans) == 1
