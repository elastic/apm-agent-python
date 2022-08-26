#  BSD 3-Clause License
#
#  Copyright (c) 2022, Elasticsearch BV
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
from collections import defaultdict

import pytest

import elasticapm
from elasticapm.conf import constants
from elasticapm.utils import encoding
from elasticapm.utils.disttracing import TraceParent


@pytest.mark.parametrize("elasticapm_client", [{"server_version": (7, 15)}, {"server_version": (7, 16)}], indirect=True)
def test_transaction_span(elasticapm_client):
    elasticapm_client.begin_transaction("test")
    with elasticapm.capture_span("test", extra={"a": "b"}):
        pass
    elasticapm_client.end_transaction("test", constants.OUTCOME.SUCCESS)
    transactions = elasticapm_client.events[constants.TRANSACTION]
    assert len(transactions) == 1
    assert transactions[0]["name"] == "test"
    assert transactions[0]["type"] == "test"
    assert transactions[0]["result"] == constants.OUTCOME.SUCCESS

    spans = elasticapm_client.events[constants.SPAN]
    assert len(spans) == 1
    assert spans[0]["name"] == "test"


@pytest.mark.parametrize(
    "elasticapm_client", [{"transactions_ignore_patterns": ["^OPTIONS", "views.api.v2"]}], indirect=True
)
def test_ignore_patterns(elasticapm_client):
    elasticapm_client.begin_transaction("web")
    elasticapm_client.end_transaction("OPTIONS views.healthcheck", 200)

    elasticapm_client.begin_transaction("web")
    elasticapm_client.end_transaction("GET views.users", 200)

    transactions = elasticapm_client.events[constants.TRANSACTION]

    assert len(transactions) == 1
    assert transactions[0]["name"] == "GET views.users"


@pytest.mark.parametrize(
    "elasticapm_client", [{"transactions_ignore_patterns": ["^OPTIONS", "views.api.v2"]}], indirect=True
)
def test_ignore_patterns_with_none_transaction_name(elasticapm_client):
    elasticapm_client.begin_transaction("web")
    t = elasticapm_client.end_transaction(None, 200)
    assert t.name == ""


@pytest.mark.parametrize(
    "elasticapm_client",
    [
        {"collect_local_variables": "errors"},
        {"collect_local_variables": "transactions", "local_var_max_length": 20, "local_var_max_list_length": 10},
        {"collect_local_variables": "all", "local_var_max_length": 20, "local_var_max_list_length": 10},
        {"collect_local_variables": "something"},
    ],
    indirect=True,
)
def test_collect_local_variables_transactions(elasticapm_client):
    mode = elasticapm_client.config.collect_local_variables
    elasticapm_client.begin_transaction("test")
    with elasticapm.capture_span("foo"):
        a_local_var = 1
        a_long_local_var = 100 * "a"
        a_long_local_list = list(range(100))
        pass
    elasticapm_client.end_transaction("test", "ok")
    frame = elasticapm_client.events[constants.SPAN][0]["stacktrace"][0]
    if mode in ("transactions", "all"):
        assert "vars" in frame, mode
        assert frame["vars"]["a_local_var"] == 1
        assert len(frame["vars"]["a_long_local_var"]) == 20
        assert len(frame["vars"]["a_long_local_list"]) == 12
        assert frame["vars"]["a_long_local_list"][-1] == "(90 more elements)"
    else:
        assert "vars" not in frame, mode


@pytest.mark.parametrize(
    "elasticapm_client",
    [
        {"source_lines_span_library_frames": 0, "source_lines_span_app_frames": 0},
        {"source_lines_span_library_frames": 1, "source_lines_span_app_frames": 1},
        {"source_lines_span_library_frames": 7, "source_lines_span_app_frames": 5},
    ],
    indirect=True,
)
def test_collect_source_transactions(elasticapm_client):
    library_frame_context = elasticapm_client.config.source_lines_span_library_frames
    in_app_frame_context = elasticapm_client.config.source_lines_span_app_frames
    elasticapm_client.begin_transaction("test")
    with elasticapm.capture_span("foo"):
        pass
    elasticapm_client.end_transaction("test", "ok")
    span = elasticapm_client.events[constants.SPAN][0]
    in_app_frame = span["stacktrace"][0]
    library_frame = span["stacktrace"][1]
    assert not in_app_frame["library_frame"]
    assert library_frame["library_frame"]
    if library_frame_context:
        assert "context_line" in library_frame, library_frame_context
        assert "pre_context" in library_frame, library_frame_context
        assert "post_context" in library_frame, library_frame_context
        lines = len([library_frame["context_line"]] + library_frame["pre_context"] + library_frame["post_context"])
        assert lines == library_frame_context, library_frame_context
    else:
        assert "context_line" not in library_frame, library_frame_context
        assert "pre_context" not in library_frame, library_frame_context
        assert "post_context" not in library_frame, library_frame_context
    if in_app_frame_context:
        assert "context_line" in in_app_frame, in_app_frame_context
        assert "pre_context" in in_app_frame, in_app_frame_context
        assert "post_context" in in_app_frame, in_app_frame_context
        lines = len([in_app_frame["context_line"]] + in_app_frame["pre_context"] + in_app_frame["post_context"])
        assert lines == in_app_frame_context, (in_app_frame_context, in_app_frame["lineno"])
    else:
        assert "context_line" not in in_app_frame, in_app_frame_context
        assert "pre_context" not in in_app_frame, in_app_frame_context
        assert "post_context" not in in_app_frame, in_app_frame_context


@pytest.mark.parametrize(
    "elasticapm_client",
    [
        {"transaction_sample_rate": 0.4, "server_version": (7, 14)},
        {"transaction_sample_rate": 0.4, "server_version": (8, 0)},
    ],
    indirect=True,
)
def test_transaction_sampling(elasticapm_client, not_so_random):
    for i in range(10):
        elasticapm_client.begin_transaction("test_type")
        with elasticapm.capture_span("xyz"):
            pass
        elasticapm_client.end_transaction("test")

    transactions = elasticapm_client.events[constants.TRANSACTION]
    spans_per_transaction = defaultdict(list)
    for span in elasticapm_client.events[constants.SPAN]:
        spans_per_transaction[span["transaction_id"]].append(span)

    # seed is fixed by not_so_random fixture
    assert len([t for t in transactions if t["sampled"]]) == 3
    if elasticapm_client.server_version < (8, 0):
        assert len(transactions) == 10
    else:
        assert len(transactions) == 3
    for transaction in transactions:
        assert transaction["sampled"] or not transaction["id"] in spans_per_transaction
        assert transaction["sampled"] or not "context" in transaction
        assert transaction["sample_rate"] == 0 if not transaction["sampled"] else transaction["sample_rate"] == 0.4


def test_transaction_sample_rate_dynamic(elasticapm_client, not_so_random):
    elasticapm_client.config.update(version="1", transaction_sample_rate=0.4)
    for i in range(10):
        elasticapm_client.begin_transaction("test_type")
        with elasticapm.capture_span("xyz"):
            pass
        elasticapm_client.end_transaction("test")

    transactions = elasticapm_client.events[constants.TRANSACTION]
    spans_per_transaction = defaultdict(list)
    for span in elasticapm_client.events[constants.SPAN]:
        spans_per_transaction[span["transaction_id"]].append(span)

    # seed is fixed by not_so_random fixture
    assert len([t for t in transactions if t["sampled"]]) == 3
    for transaction in transactions:
        assert transaction["sampled"] or not transaction["id"] in spans_per_transaction
        assert transaction["sampled"] or not "context" in transaction

    elasticapm_client.config.update(version="1", transaction_sample_rate=1.0)
    for i in range(5):
        elasticapm_client.begin_transaction("test_type")
        with elasticapm.capture_span("xyz"):
            pass
        elasticapm_client.end_transaction("test")

    transactions = elasticapm_client.events[constants.TRANSACTION]

    # seed is fixed by not_so_random fixture
    assert len([t for t in transactions if t["sampled"]]) == 8


def test_transaction_max_spans_dynamic(elasticapm_client):
    elasticapm_client.config.update(version=1, transaction_max_spans=1)
    elasticapm_client.begin_transaction("test_type")
    for i in range(5):
        with elasticapm.capture_span("span"):
            pass
    elasticapm_client.end_transaction("test")
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 1

    elasticapm_client.config.update(version=2, transaction_max_spans=3)
    elasticapm_client.begin_transaction("test_type")
    for i in range(5):
        with elasticapm.capture_span("span"):
            pass

    elasticapm_client.end_transaction("test")
    transaction = elasticapm_client.events[constants.TRANSACTION][1]
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 3


@pytest.mark.parametrize("elasticapm_client", [{"span_stack_trace_min_duration": 20}], indirect=True)
def test_transaction_span_stack_trace_min_duration(elasticapm_client):
    elasticapm_client.begin_transaction("test_type")
    with elasticapm.capture_span("noframes", duration=0.001):
        pass
    with elasticapm.capture_span("frames", duration=0.04):
        pass
    elasticapm_client.end_transaction("test")

    spans = elasticapm_client.events[constants.SPAN]

    assert len(spans) == 2
    assert spans[0]["name"] == "noframes"
    assert "stacktrace" not in spans[0]

    assert spans[1]["name"] == "frames"
    assert spans[1]["stacktrace"] is not None


@pytest.mark.parametrize("elasticapm_client", [{"span_stack_trace_min_duration": 0}], indirect=True)
def test_transaction_span_stack_trace_min_duration_no_limit(elasticapm_client):
    elasticapm_client.begin_transaction("test_type")
    with elasticapm.capture_span("frames"):
        pass
    with elasticapm.capture_span("frames", duration=0.04):
        pass
    elasticapm_client.end_transaction("test")

    spans = elasticapm_client.events[constants.SPAN]

    assert len(spans) == 2
    assert spans[0]["name"] == "frames"
    assert spans[0]["stacktrace"] is not None

    assert spans[1]["name"] == "frames"
    assert spans[1]["stacktrace"] is not None


def test_transaction_span_stack_trace_min_duration_dynamic(elasticapm_client):
    elasticapm_client.config.update(version="1", span_stack_trace_min_duration=20)
    elasticapm_client.begin_transaction("test_type")
    with elasticapm.capture_span("noframes", duration=0.001):
        pass
    with elasticapm.capture_span("frames", duration=0.04):
        pass
    elasticapm_client.end_transaction("test")

    spans = elasticapm_client.events[constants.SPAN]

    assert len(spans) == 2
    assert spans[0]["name"] == "noframes"
    assert "stacktrace" not in spans[0]

    assert spans[1]["name"] == "frames"
    assert spans[1]["stacktrace"] is not None

    elasticapm_client.config.update(version="1", span_stack_trace_min_duration=0)
    elasticapm_client.begin_transaction("test_type")
    with elasticapm.capture_span("frames"):
        pass
    with elasticapm.capture_span("frames", duration=0.04):
        pass
    elasticapm_client.end_transaction("test")

    spans = elasticapm_client.events[constants.SPAN]

    assert len(spans) == 4
    assert spans[2]["name"] == "frames"
    assert spans[2]["stacktrace"] is not None

    assert spans[3]["name"] == "frames"
    assert spans[3]["stacktrace"] is not None


def test_transaction_span_stack_trace_min_duration_overrides_old_config(elasticapm_client):
    """
    span_stack_trace_min_duration overrides span_frames_min_duration (which is deprecated)
    """
    elasticapm_client.config.update(version="1", span_stack_trace_min_duration=20, span_frames_min_duration=1)
    elasticapm_client.begin_transaction("test_type")
    with elasticapm.capture_span("noframes", duration=0.01):
        pass
    with elasticapm.capture_span("frames", duration=0.04):
        pass
    elasticapm_client.end_transaction("test")

    spans = elasticapm_client.events[constants.SPAN]

    assert len(spans) == 2
    assert spans[0]["name"] == "noframes"
    assert "stacktrace" not in spans[0]

    assert spans[1]["name"] == "frames"
    assert spans[1]["stacktrace"] is not None

    # Set span_stack_trace_min_duration to default so it picks up the non-default span_frames_min_duration
    elasticapm_client.config.update(version="1", span_stack_trace_min_duration=5, span_frames_min_duration=1)
    elasticapm_client.begin_transaction("test_type")
    with elasticapm.capture_span("yesframes", duration=0.01):
        pass
    with elasticapm.capture_span("frames", duration=0.04):
        pass
    elasticapm_client.end_transaction("test")

    spans = elasticapm_client.events[constants.SPAN]

    assert len(spans) == 4
    assert spans[2]["name"] == "yesframes"
    assert spans[2]["stacktrace"] is not None

    assert spans[3]["name"] == "frames"
    assert spans[3]["stacktrace"] is not None


def test_transaction_keyword_truncation(elasticapm_client):
    too_long = "x" * (constants.KEYWORD_MAX_LENGTH + 1)
    expected = encoding.keyword_field(too_long)
    assert too_long != expected
    assert len(expected) == constants.KEYWORD_MAX_LENGTH
    assert expected[-1] != "x"
    elasticapm_client.begin_transaction(too_long)
    elasticapm.label(val=too_long)
    elasticapm.set_user_context(username=too_long, email=too_long, user_id=too_long)
    with elasticapm.capture_span(name=too_long, span_type=too_long):
        pass
    elasticapm_client.end_transaction(too_long, too_long)
    elasticapm_client.close()

    span = elasticapm_client.events["span"][0]
    transaction = elasticapm_client.events["transaction"][0]

    assert transaction["name"] == expected
    assert transaction["type"] == expected
    assert transaction["result"] == expected

    assert transaction["context"]["user"]["id"] == expected
    assert transaction["context"]["user"]["username"] == expected
    assert transaction["context"]["user"]["email"] == expected

    assert transaction["context"]["tags"]["val"] == expected

    assert span["type"] == expected
    assert span["name"] == expected


def test_trace_parent(elasticapm_client):
    trace_parent = TraceParent.from_string("00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03")
    elasticapm_client.begin_transaction("test", trace_parent=trace_parent)
    transaction = elasticapm_client.end_transaction("test", "OK")
    data = transaction.to_dict()
    assert data["trace_id"] == "0af7651916cd43dd8448eb211c80319c"
    assert data["parent_id"] == "b7ad6b7169203331"


def test_sample_rate_in_dict(elasticapm_client):
    trace_parent = TraceParent.from_string(
        "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03", tracestate_string="es=s:0.43"
    )
    elasticapm_client.begin_transaction("test", trace_parent=trace_parent)
    with elasticapm.capture_span("x"):
        pass
    transaction = elasticapm_client.end_transaction("test", "OK")
    data = transaction.to_dict()
    assert data["sample_rate"] == 0.43
    assert elasticapm_client.events[constants.SPAN][0]["sample_rate"] == 0.43


def test_sample_rate_undefined_by_parent(elasticapm_client):
    trace_parent = TraceParent.from_string("00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03")
    elasticapm_client.begin_transaction("test", trace_parent=trace_parent)
    with elasticapm.capture_span("x"):
        pass
    transaction = elasticapm_client.end_transaction("test", "OK")
    data = transaction.to_dict()
    assert "sample_rate" not in data
    assert "sample_rate" not in elasticapm_client.events[constants.SPAN][0]


def test_trace_parent_not_set(elasticapm_client):
    elasticapm_client.begin_transaction("test", trace_parent=None)
    transaction = elasticapm_client.end_transaction("test", "OK")
    data = transaction.to_dict()
    assert data["trace_id"] is not None
    assert "parent_id" not in data


def test_ensure_parent_sets_new_id(elasticapm_client):
    transaction = elasticapm_client.begin_transaction("test", trace_parent=None)
    assert transaction.id == transaction.trace_parent.span_id
    span_id = transaction.ensure_parent_id()
    assert span_id == transaction.trace_parent.span_id


def test_ensure_parent_doesnt_change_existing_id(elasticapm_client):
    transaction = elasticapm_client.begin_transaction("test", trace_parent=None)
    assert transaction.id == transaction.trace_parent.span_id
    span_id = transaction.ensure_parent_id()
    span_id_2 = transaction.ensure_parent_id()
    assert span_id == span_id_2


def test_backdating_transaction(elasticapm_client):
    elasticapm_client.begin_transaction("test", start=time.time() - 1)
    elasticapm_client.end_transaction()
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    assert 1000 < transaction["duration"] < 2000


def test_transaction_span_links(elasticapm_client):
    tp1 = TraceParent.from_string("00-aabbccddeeff00112233445566778899-0011223344556677-01")
    tp2 = TraceParent.from_string("00-00112233445566778899aabbccddeeff-aabbccddeeff0011-01")
    elasticapm_client.begin_transaction("a", links=[tp1, tp2])
    with elasticapm.capture_span("a", links=(tp1, tp2)):
        pass
    elasticapm_client.end_transaction("foo")
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    span = elasticapm_client.events[constants.SPAN][0]
    assert transaction["links"][0]["trace_id"] == "aabbccddeeff00112233445566778899"
    assert transaction["links"][0]["span_id"] == "0011223344556677"
    assert transaction["links"][1]["trace_id"] == "00112233445566778899aabbccddeeff"
    assert transaction["links"][1]["span_id"] == "aabbccddeeff0011"

    assert span["links"][0]["trace_id"] == "aabbccddeeff00112233445566778899"
    assert span["links"][0]["span_id"] == "0011223344556677"
    assert span["links"][1]["trace_id"] == "00112233445566778899aabbccddeeff"
    assert span["links"][1]["span_id"] == "aabbccddeeff0011"


def test_transaction_trace_continuation_continue(elasticapm_client):
    elasticapm_client.config.update("1", trace_continuation_strategy=constants.TRACE_CONTINUATION_STRATEGY.CONTINUE)
    tp = TraceParent.from_string("00-aabbccddeeff00112233445566778899-0011223344556677-01")
    elasticapm_client.begin_transaction("a", trace_parent=tp)
    elasticapm_client.end_transaction("foo")
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    assert transaction["trace_id"] == tp.trace_id
    assert "links" not in transaction


def test_transaction_trace_continuation_restart(elasticapm_client):
    elasticapm_client.config.update("1", trace_continuation_strategy=constants.TRACE_CONTINUATION_STRATEGY.RESTART)
    tp = TraceParent.from_string("00-aabbccddeeff00112233445566778899-0011223344556677-01")
    elasticapm_client.begin_transaction("a", trace_parent=tp)
    elasticapm_client.end_transaction("foo")
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    assert transaction["trace_id"] != tp.trace_id
    assert transaction["links"][0]["trace_id"] == tp.trace_id
    assert transaction["links"][0]["span_id"] == tp.span_id


def test_transaction_trace_continuation_restart_external(elasticapm_client):
    elasticapm_client.config.update(
        "1", trace_continuation_strategy=constants.TRACE_CONTINUATION_STRATEGY.RESTART_EXTERNAL
    )
    tp = TraceParent.from_string("00-aabbccddeeff00112233445566778899-0011223344556677-01")
    elasticapm_client.begin_transaction("a", trace_parent=tp)
    elasticapm_client.end_transaction("foo")
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    assert transaction["trace_id"] != tp.trace_id
    assert transaction["links"][0]["trace_id"] == tp.trace_id
    assert transaction["links"][0]["span_id"] == tp.span_id

    tp.add_tracestate("foo", "bar")
    elasticapm_client.begin_transaction("a", trace_parent=tp)
    elasticapm_client.end_transaction("foo")
    transaction = elasticapm_client.events[constants.TRANSACTION][1]
    assert transaction["trace_id"] == tp.trace_id
    assert "links" not in transaction
