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
import time

import mock
import pytest

import elasticapm
from elasticapm.utils import compat


def test_bare_transaction(elasticapm_client):
    elasticapm_client.begin_transaction("request", start=0)
    elasticapm_client.end_transaction("test", "OK", duration=5)
    breakdown = elasticapm_client._metrics.get_metricset("elasticapm.metrics.sets.breakdown.BreakdownMetricSet")
    data = list(breakdown.collect())
    assert len(data) == 2
    asserts = 0
    for elem in data:
        if "transaction.breakdown.count" in elem["samples"]:
            assert elem["samples"]["transaction.breakdown.count"]["value"] == 1
            assert elem["transaction"] == {"name": "test", "type": "request"}
            asserts += 1
        elif "span.self_time.sum.us" in elem["samples"]:
            assert elem["samples"]["span.self_time.count"]["value"] == 1
            assert elem["samples"]["span.self_time.sum.us"]["value"] == 5000000
            assert elem["transaction"] == {"name": "test", "type": "request"}
            assert elem["span"] == {"subtype": "", "type": "app"}
            asserts += 1
    assert asserts == 2

    transaction_metrics = elasticapm_client._metrics.get_metricset(
        "elasticapm.metrics.sets.transactions.TransactionsMetricSet"
    )
    transaction_data = list(transaction_metrics.collect())
    assert len(transaction_data) == 1
    assert transaction_data[0]["samples"]["transaction.duration.sum.us"]["value"] == 5000000


def test_single_span(elasticapm_client):
    elasticapm_client.begin_transaction("request", start=0)
    with elasticapm.capture_span("test", span_type="db", span_subtype="mysql", start=10, duration=5):
        pass
    elasticapm_client.end_transaction("test", "OK", duration=15)
    breakdown = elasticapm_client._metrics.get_metricset("elasticapm.metrics.sets.breakdown.BreakdownMetricSet")
    data = list(breakdown.collect())
    assert len(data) == 3
    asserts = 0
    for elem in data:
        if "transaction.breakdown.count" in elem["samples"]:
            assert elem["samples"]["transaction.breakdown.count"]["value"] == 1
            assert elem["transaction"] == {"name": "test", "type": "request"}
            asserts += 1
        elif "span.self_time.sum.us" in elem["samples"]:
            if elem["span"] == {"type": "app", "subtype": ""}:
                assert elem["transaction"] == {"name": "test", "type": "request"}
                assert elem["samples"]["span.self_time.sum.us"]["value"] == 10000000
                assert elem["samples"]["span.self_time.count"]["value"] == 1
                asserts += 1
            elif elem["span"] == {"type": "db", "subtype": "mysql"}:
                assert elem["samples"]["span.self_time.count"]["value"] == 1
                assert elem["samples"]["span.self_time.sum.us"]["value"] == 5000000
                assert elem["transaction"] == {"name": "test", "type": "request"}
                asserts += 1
    assert asserts == 3

    transaction_metrics = elasticapm_client._metrics.get_metricset(
        "elasticapm.metrics.sets.transactions.TransactionsMetricSet"
    )
    transaction_data = list(transaction_metrics.collect())
    assert len(transaction_data) == 1
    assert transaction_data[0]["samples"]["transaction.duration.sum.us"]["value"] == 15000000


def test_nested_spans(elasticapm_client):
    elasticapm_client.begin_transaction("request", start=0)
    with elasticapm.capture_span("test", span_type="template", span_subtype="django", start=5, duration=15):
        with elasticapm.capture_span("test", span_type="db", span_subtype="mysql", start=10, duration=5):
            pass
        with elasticapm.capture_span("test", span_type="db", span_subtype="mysql", start=15, duration=5):
            pass
    elasticapm_client.end_transaction("test", "OK", duration=25)
    breakdown = elasticapm_client._metrics.get_metricset("elasticapm.metrics.sets.breakdown.BreakdownMetricSet")
    data = list(breakdown.collect())
    assert len(data) == 4
    asserts = 0
    for elem in data:
        if "transaction.breakdown.count" in elem["samples"]:
            assert elem["samples"]["transaction.breakdown.count"]["value"] == 1
            assert elem["transaction"] == {"name": "test", "type": "request"}
            asserts += 1
        elif "span.self_time.sum.us" in elem["samples"]:
            if elem["span"] == {"type": "app", "subtype": ""}:
                assert elem["transaction"] == {"name": "test", "type": "request"}
                assert elem["samples"]["span.self_time.sum.us"]["value"] == 10000000
                assert elem["samples"]["span.self_time.count"]["value"] == 1
                asserts += 1
            elif elem["span"] == {"type": "db", "subtype": "mysql"}:
                assert elem["samples"]["span.self_time.count"]["value"] == 2
                assert elem["samples"]["span.self_time.sum.us"]["value"] == 10000000
                assert elem["transaction"] == {"name": "test", "type": "request"}
                asserts += 1
            elif elem["span"] == {"type": "template", "subtype": "django"}:
                assert elem["samples"]["span.self_time.count"]["value"] == 1
                assert elem["samples"]["span.self_time.sum.us"]["value"] == 5000000
                assert elem["transaction"] == {"name": "test", "type": "request"}
                asserts += 1
    assert asserts == 4

    transaction_metrics = elasticapm_client._metrics.get_metricset(
        "elasticapm.metrics.sets.transactions.TransactionsMetricSet"
    )
    transaction_data = list(transaction_metrics.collect())
    assert len(transaction_data) == 1
    assert transaction_data[0]["samples"]["transaction.duration.sum.us"]["value"] == 25000000


def test_explicit_app_span(elasticapm_client):
    transaction = elasticapm_client.begin_transaction("request")
    with elasticapm.capture_span("test", span_type="app"):
        pass
    elasticapm_client.end_transaction("test", "OK")
    breakdown = elasticapm_client._metrics.get_metricset("elasticapm.metrics.sets.breakdown.BreakdownMetricSet")
    data = list(breakdown.collect())
    assert len(data) == 2
    asserts = 0
    for elem in data:
        if "transaction.breakdown.count" in elem["samples"]:
            assert elem["samples"]["transaction.breakdown.count"]["value"] == 1
            assert elem["transaction"] == {"name": "test", "type": "request"}
            asserts += 1
        elif "span.self_time.sum.us" in elem["samples"]:
            if elem["span"] == {"type": "app", "subtype": ""}:
                assert elem["transaction"] == {"name": "test", "type": "request"}
                assert elem["samples"]["span.self_time.count"]["value"] == 2
                asserts += 1
    assert asserts == 2


@pytest.mark.parametrize("elasticapm_client", [{"breakdown_metrics": False}], indirect=True)
def test_disable_breakdowns(elasticapm_client):
    with pytest.raises(LookupError):
        elasticapm_client._metrics.get_metricset("elasticapm.metrics.sets.breakdown.BreakdownMetricSet")
    transaction_metrics = elasticapm_client._metrics.get_metricset(
        "elasticapm.metrics.sets.transactions.TransactionsMetricSet"
    )
    with mock.patch("elasticapm.traces.BaseSpan.child_started") as mock_child_started, mock.patch(
        "elasticapm.traces.BaseSpan.child_ended"
    ) as mock_child_ended, mock.patch("elasticapm.traces.Transaction.track_span_duration") as mock_track_span_duration:
        transaction = elasticapm_client.begin_transaction("test")
        assert transaction._breakdown is None
        with elasticapm.capture_span("test", span_type="template", span_subtype="django", duration=5):
            pass
        elasticapm_client.end_transaction("test", "OK", duration=5)
        assert mock_child_started.call_count == 0
        assert mock_child_ended.call_count == 0
        assert mock_track_span_duration.call_count == 0
    # transaction duration should still be captured
    data = list(transaction_metrics.collect())
    assert len(data) == 1
    assert data[0]["samples"]["transaction.duration.sum.us"]["value"] == 5000000


def test_metrics_reset_after_collect(elasticapm_client):
    elasticapm_client.begin_transaction("request")
    with elasticapm.capture_span("test", span_type="db", span_subtype="mysql", duration=5):
        pass
    elasticapm_client.end_transaction("test", "OK", duration=15)
    breakdown = elasticapm_client._metrics.get_metricset("elasticapm.metrics.sets.breakdown.BreakdownMetricSet")
    transaction_metrics = elasticapm_client._metrics.get_metricset(
        "elasticapm.metrics.sets.transactions.TransactionsMetricSet"
    )
    for metricset in (breakdown, transaction_metrics):
        for labels, c in compat.iteritems(metricset._counters):
            assert c.val != 0
        for labels, t in compat.iteritems(metricset._timers):
            assert t.val != (0, 0)
        list(metricset.collect())
        for labels, c in compat.iteritems(metricset._counters):
            assert c.val == 0
        for labels, t in compat.iteritems(metricset._timers):
            assert t.val == (0, 0)


def test_multiple_transactions(elasticapm_client):
    for i in (1, 2):
        elasticapm_client.begin_transaction("request")
        with elasticapm.capture_span("test", duration=5):
            pass
        elasticapm_client.end_transaction("test", "OK", duration=10)

    breakdown = elasticapm_client._metrics.get_metricset("elasticapm.metrics.sets.breakdown.BreakdownMetricSet")
    data = list(breakdown.collect())
    asserts = 0
    for elem in data:
        if "transaction.breakdown.count" in elem["samples"]:
            assert elem["samples"]["transaction.breakdown.count"]["value"] == 2
            assert elem["transaction"] == {"name": "test", "type": "request"}
            asserts += 1
        elif "span.self_time.sum.us" in elem["samples"]:
            if elem["span"] == {"type": "app", "subtype": ""}:
                assert elem["transaction"] == {"name": "test", "type": "request"}
                # precision lost due to float arithmetic
                assert 9999999 <= elem["samples"]["span.self_time.sum.us"]["value"] <= 10000000
                assert elem["samples"]["span.self_time.count"]["value"] == 2
                asserts += 1
            elif elem["span"] == {"type": "code", "subtype": "custom"}:
                assert elem["transaction"] == {"name": "test", "type": "request"}
                assert 9999999 <= elem["samples"]["span.self_time.sum.us"]["value"] <= 10000000
                assert elem["samples"]["span.self_time.count"]["value"] == 2
                asserts += 1
    assert asserts == 3

    transaction_metrics = elasticapm_client._metrics.get_metricset(
        "elasticapm.metrics.sets.transactions.TransactionsMetricSet"
    )
    transaction_data = list(transaction_metrics.collect())
    assert len(transaction_data) == 1
    assert 19999999 <= transaction_data[0]["samples"]["transaction.duration.sum.us"]["value"] <= 20000000
    assert transaction_data[0]["samples"]["transaction.duration.count"]["value"] == 2
