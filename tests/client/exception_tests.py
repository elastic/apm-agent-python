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

import os

import mock
import pytest

import elasticapm
from elasticapm.conf.constants import ERROR, KEYWORD_MAX_LENGTH
from elasticapm.utils import compat, encoding
from tests.utils.stacks import get_me_more_test_frames


def test_explicit_message_on_exception_event(elasticapm_client):
    try:
        raise ValueError("foo")
    except ValueError:
        elasticapm_client.capture("Exception", message="foobar")

    assert len(elasticapm_client.events) == 1
    event = elasticapm_client.events[ERROR][0]
    assert event["exception"]["message"] == "foobar"


@pytest.mark.parametrize(
    "elasticapm_client",
    [{"include_paths": ("tests",), "local_var_max_length": 20, "local_var_list_max_length": 10}],
    indirect=True,
)
def test_exception_event(elasticapm_client):
    try:
        a_local_var = 1
        a_long_local_var = 100 * "a"
        a_long_local_list = list(range(100))
        raise ValueError("foo")
    except ValueError:
        elasticapm_client.capture("Exception")

    assert len(elasticapm_client.events) == 1
    event = elasticapm_client.events[ERROR][0]
    assert "exception" in event
    exc = event["exception"]
    assert exc["message"] == "ValueError: foo"
    assert exc["type"] == "ValueError"
    assert exc["module"] == ValueError.__module__  # this differs in some Python versions
    assert "stacktrace" in exc
    frames = exc["stacktrace"]
    assert len(frames) == 1
    frame = frames[0]
    assert frame["abs_path"], __file__.replace(".pyc" == ".py")
    assert frame["filename"] == os.path.join("tests", "client", "exception_tests.py")
    assert frame["module"] == __name__
    assert frame["function"] == "test_exception_event"
    assert not frame["library_frame"]
    assert frame["vars"]["a_local_var"] == 1
    assert len(frame["vars"]["a_long_local_var"]) == 20
    assert len(frame["vars"]["a_long_local_list"]) == 12
    assert frame["vars"]["a_long_local_list"][-1] == "(90 more elements)"
    assert "timestamp" in event
    assert "log" not in event
    # check that only frames from `tests` module are not marked as library frames
    assert all(
        frame["library_frame"] or frame["module"].startswith("tests") for frame in event["exception"]["stacktrace"]
    )


def test_sending_exception(sending_elasticapm_client):
    try:
        1 / 0
    except Exception:
        sending_elasticapm_client.capture_exception()
    sending_elasticapm_client.close()
    assert (
        sending_elasticapm_client.httpserver.responses[0]["code"] == 202
    ), sending_elasticapm_client.httpserver.responses[0]


@pytest.mark.parametrize(
    "elasticapm_client",
    [{"include_paths": ("*/tests/*",), "local_var_max_length": 20, "local_var_list_max_length": 10}],
    indirect=True,
)
def test_message_event(elasticapm_client):
    a_local_var = 1
    a_long_local_var = 100 * "a"
    a_long_local_list = list(range(100))
    elasticapm_client.capture("Message", message="test")

    assert len(elasticapm_client.events) == 1
    event = elasticapm_client.events[ERROR][0]
    assert event["log"]["message"] == "test"
    assert "stacktrace" not in event
    assert "timestamp" in event
    assert "stacktrace" in event["log"]
    # check that only frames from `tests` module are not marked as library frames
    for frame in event["log"]["stacktrace"]:
        assert frame["library_frame"] or frame["module"].startswith(("tests", "__main__")), (
            frame["module"],
            frame["abs_path"],
        )
    frame = event["log"]["stacktrace"][0]
    assert frame["vars"]["a_local_var"] == 1
    assert len(frame["vars"]["a_long_local_var"]) == 20
    assert len(frame["vars"]["a_long_local_list"]) == 12
    assert frame["vars"]["a_long_local_list"][-1] == "(90 more elements)"


def test_param_message_event(elasticapm_client):
    elasticapm_client.capture("Message", param_message={"message": "test %s %d", "params": ("x", 1)})

    assert len(elasticapm_client.events[ERROR]) == 1
    event = elasticapm_client.events[ERROR][0]
    assert event["log"]["message"] == "test x 1"
    assert event["log"]["param_message"] == "test %s %d"


def test_message_with_percent(elasticapm_client):
    elasticapm_client.capture("Message", message="This works 100% of the time")

    assert len(elasticapm_client.events[ERROR]) == 1
    event = elasticapm_client.events[ERROR][0]
    assert event["log"]["message"] == "This works 100% of the time"
    assert event["log"]["param_message"] == "This works 100% of the time"


def test_logger(elasticapm_client):
    elasticapm_client.capture("Message", message="test", logger_name="test")

    assert len(elasticapm_client.events[ERROR]) == 1
    event = elasticapm_client.events[ERROR][0]
    assert event["log"]["logger_name"] == "test"
    assert "timestamp" in event


@pytest.mark.parametrize(
    "elasticapm_client",
    [
        {"collect_local_variables": "errors"},
        {"collect_local_variables": "transactions"},
        {"collect_local_variables": "all"},
        {"collect_local_variables": "something"},
    ],
    indirect=True,
)
def test_collect_local_variables_errors(elasticapm_client):
    mode = elasticapm_client.config.collect_local_variables
    try:
        1 / 0
    except ZeroDivisionError:
        elasticapm_client.capture_exception()
    event = elasticapm_client.events[ERROR][0]
    if mode in ("errors", "all"):
        assert "vars" in event["exception"]["stacktrace"][0], mode
    else:
        assert "vars" not in event["exception"]["stacktrace"][0], mode


@pytest.mark.parametrize(
    "elasticapm_client",
    [
        {"source_lines_error_library_frames": 0, "source_lines_error_app_frames": 0},
        {"source_lines_error_library_frames": 1, "source_lines_error_app_frames": 1},
        {"source_lines_error_library_frames": 7, "source_lines_error_app_frames": 3},
    ],
    indirect=True,
)
def test_collect_source_errors(elasticapm_client):
    library_frame_context = elasticapm_client.config.source_lines_error_library_frames
    in_app_frame_context = elasticapm_client.config.source_lines_error_app_frames
    try:
        import json, datetime

        json.dumps(datetime.datetime.now())
    except TypeError:
        elasticapm_client.capture_exception()
    event = elasticapm_client.events[ERROR][0]
    in_app_frame = event["exception"]["stacktrace"][0]
    library_frame = event["exception"]["stacktrace"][1]
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


def test_transaction_data_is_attached_to_errors_no_transaction(elasticapm_client):
    elasticapm_client.capture_message("noid")
    elasticapm_client.begin_transaction("test")
    elasticapm_client.end_transaction("test", "test")
    elasticapm_client.capture_message("noid")

    errors = elasticapm_client.events[ERROR]
    assert "transaction_id" not in errors[0]
    assert "transaction_id" not in errors[1]


def test_transaction_data_is_attached_to_errors_message_outside_span(elasticapm_client):
    elasticapm_client.begin_transaction("test")
    elasticapm_client.capture_message("outside_span")
    transaction = elasticapm_client.end_transaction("test", "test")

    error = elasticapm_client.events[ERROR][0]
    assert error["transaction_id"] == transaction.id
    assert error["parent_id"] == transaction.id
    assert error["transaction"]["sampled"]
    assert error["transaction"]["type"] == "test"


def test_transaction_data_is_attached_to_errors_message_in_span(elasticapm_client):
    elasticapm_client.begin_transaction("test")

    with elasticapm.capture_span("in_span_handler_test") as span_obj:
        elasticapm_client.capture_message("in_span")

    transaction = elasticapm_client.end_transaction("test", "test")

    error = elasticapm_client.events[ERROR][0]

    assert error["transaction_id"] == transaction.id
    assert error["parent_id"] == span_obj.id
    assert error["transaction"]["sampled"]
    assert error["transaction"]["type"] == "test"


def test_transaction_data_is_attached_to_errors_exc_handled_in_span(elasticapm_client):
    elasticapm_client.begin_transaction("test")
    with elasticapm.capture_span("in_span_handler_test") as span_obj:
        try:
            assert False
        except AssertionError:
            elasticapm_client.capture_exception()
    transaction = elasticapm_client.end_transaction("test", "test")

    error = elasticapm_client.events[ERROR][0]

    assert error["transaction_id"] == transaction.id
    assert error["parent_id"] == span_obj.id
    assert error["transaction"]["sampled"]
    assert error["transaction"]["type"] == "test"


def test_transaction_data_is_attached_to_errors_exc_handled_outside_span(elasticapm_client):
    elasticapm_client.begin_transaction("test")
    try:
        with elasticapm.capture_span("out_of_span_handler_test") as span_obj:
            assert False
    except AssertionError:
        elasticapm_client.capture_exception()
    transaction = elasticapm_client.end_transaction("test", "test")

    error = elasticapm_client.events[ERROR][0]

    assert error["transaction_id"] == transaction.id
    assert error["parent_id"] == span_obj.id
    assert error["transaction"]["sampled"]
    assert error["transaction"]["type"] == "test"


def test_transaction_context_is_used_in_errors(elasticapm_client):
    elasticapm_client.begin_transaction("test")
    elasticapm.tag(foo="baz")
    elasticapm.set_custom_context({"a": "b"})
    elasticapm.set_user_context(username="foo", email="foo@example.com", user_id=42)
    elasticapm_client.capture_message("x", custom={"foo": "bar"})
    transaction = elasticapm_client.end_transaction("test", "OK")
    message = elasticapm_client.events[ERROR][0]
    assert message["context"]["custom"] == {"a": "b", "foo": "bar"}
    assert message["context"]["user"] == {"username": "foo", "email": "foo@example.com", "id": 42}
    assert message["context"]["tags"] == {"foo": "baz"}
    assert "a" in transaction.context["custom"]
    assert "foo" not in transaction.context["custom"]


def test_error_keyword_truncation(sending_elasticapm_client):
    too_long = "x" * (KEYWORD_MAX_LENGTH + 1)
    expected = encoding.keyword_field(too_long)

    # let's create a way too long Exception type with a way too long module name
    WayTooLongException = type(too_long.upper(), (Exception,), {})
    WayTooLongException.__module__ = too_long
    try:
        raise WayTooLongException()
    except WayTooLongException:
        with mock.patch("elasticapm.events.get_culprit") as mock_get_culprit:
            mock_get_culprit.return_value = too_long
            sending_elasticapm_client.capture_exception(handled=False)
    sending_elasticapm_client.close()
    error = sending_elasticapm_client.httpserver.payloads[0][1]["error"]

    assert error["exception"]["type"] == expected.upper()
    assert error["exception"]["module"] == expected
    assert error["culprit"] == expected


def test_message_keyword_truncation(sending_elasticapm_client):
    too_long = "x" * (KEYWORD_MAX_LENGTH + 1)
    expected = encoding.keyword_field(too_long)
    sending_elasticapm_client.capture_message(
        param_message={"message": too_long, "params": []}, logger_name=too_long, handled=False
    )
    sending_elasticapm_client.close()
    error = sending_elasticapm_client.httpserver.payloads[0][1]["error"]

    assert error["log"]["param_message"] == expected
    assert error["log"]["message"] == too_long  # message is not truncated

    assert error["log"]["logger_name"] == expected


@pytest.mark.parametrize("elasticapm_client", [{"stack_trace_limit": 10}], indirect=True)
def test_stack_trace_limit(elasticapm_client):
    def func():
        1 / 0  # I'm the context line of the last frame!

    try:
        list(get_me_more_test_frames(15, func))
    except ZeroDivisionError:
        elasticapm_client.capture_exception()
    exception = elasticapm_client.events[ERROR][-1]
    frames = exception["exception"]["stacktrace"]
    assert len(frames) == 10
    assert "I'm the context line of the last frame" in frames[-1]["context_line"]

    elasticapm_client.config.update("1", stack_trace_limit=-1)
    try:
        list(get_me_more_test_frames(15, func))
    except ZeroDivisionError:
        elasticapm_client.capture_exception()
    exception = elasticapm_client.events[ERROR][-1]
    frames = exception["exception"]["stacktrace"]
    assert len(frames) > 15
    assert "I'm the context line of the last frame" in frames[-1]["context_line"]

    elasticapm_client.config.update("1", stack_trace_limit=0)
    try:
        list(get_me_more_test_frames(15, func))
    except ZeroDivisionError:
        elasticapm_client.capture_exception()
    exception = elasticapm_client.events[ERROR][-1]
    frames = exception["exception"]["stacktrace"]
    assert len(frames) == 0
