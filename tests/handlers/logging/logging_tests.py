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
import sys
import warnings
from logging import LogRecord

import pytest

from elasticapm.conf import Config
from elasticapm.conf.constants import ERROR
from elasticapm.handlers.logging import Formatter, LoggingFilter, LoggingHandler
from elasticapm.handlers.structlog import structlog_processor
from elasticapm.traces import Tracer, capture_span
from elasticapm.utils import compat
from elasticapm.utils.stacks import iter_stack_frames
from tests.fixtures import TempStoreClient


@pytest.fixture()
def logger(elasticapm_client):
    elasticapm_client.config.include_paths = ["tests", "elasticapm"]
    handler = LoggingHandler(elasticapm_client)
    logger = logging.getLogger(__name__)
    logger.handlers = []
    logger.addHandler(handler)
    logger.client = elasticapm_client
    logger.level = logging.INFO
    return logger


def test_logger_basic(logger):
    logger.error("This is a test error")

    assert len(logger.client.events) == 1
    event = logger.client.events[ERROR][0]
    assert event["log"]["logger_name"] == __name__
    assert event["log"]["level"] == "error"
    assert event["log"]["message"] == "This is a test error"
    assert "stacktrace" in event["log"]
    assert "exception" not in event
    assert "param_message" in event["log"]
    assert event["log"]["param_message"] == "This is a test error"


def test_logger_warning(logger):
    logger.warning("This is a test warning")
    assert len(logger.client.events) == 1
    event = logger.client.events[ERROR][0]
    assert event["log"]["logger_name"] == __name__
    assert event["log"]["level"] == "warning"
    assert "exception" not in event
    assert "param_message" in event["log"]
    assert event["log"]["param_message"] == "This is a test warning"


def test_logger_extra_data(logger):
    logger.info("This is a test info with a url", extra=dict(data=dict(url="http://example.com")))
    assert len(logger.client.events) == 1
    event = logger.client.events[ERROR][0]
    assert event["context"]["custom"]["url"] == "http://example.com"
    assert "stacktrace" in event["log"]
    assert "exception" not in event
    assert "param_message" in event["log"]
    assert event["log"]["param_message"] == "This is a test info with a url"


def test_logger_exc_info(logger):
    try:
        raise ValueError("This is a test ValueError")
    except ValueError:
        logger.info("This is a test info with an exception", exc_info=True)

    assert len(logger.client.events) == 1
    event = logger.client.events[ERROR][0]

    # assert event['message'] == 'This is a test info with an exception'
    assert "exception" in event
    assert "stacktrace" in event["exception"]
    exc = event["exception"]
    assert exc["type"] == "ValueError"
    assert exc["message"] == "ValueError: This is a test ValueError"
    assert "param_message" in event["log"]
    assert event["log"]["message"] == "This is a test info with an exception"


def test_message_params(logger):
    logger.info("This is a test of %s", "args")
    assert len(logger.client.events) == 1
    event = logger.client.events[ERROR][0]
    assert "exception" not in event
    assert "param_message" in event["log"]
    assert event["log"]["message"] == "This is a test of args"
    assert event["log"]["param_message"] == "This is a test of %s"


def test_record_stack(logger):
    logger.info("This is a test of stacks", extra={"stack": True})
    assert len(logger.client.events) == 1
    event = logger.client.events[ERROR][0]
    frames = event["log"]["stacktrace"]
    assert len(frames) != 1
    frame = frames[0]
    assert frame["module"] == __name__
    assert "exception" not in event
    assert "param_message" in event["log"]
    assert event["log"]["param_message"] == "This is a test of stacks"
    assert event["culprit"] == "tests.handlers.logging.logging_tests.test_record_stack"
    assert event["log"]["message"] == "This is a test of stacks"


def test_no_record_stack(logger):
    logger.info("This is a test of no stacks", extra={"stack": False})
    assert len(logger.client.events) == 1
    event = logger.client.events[ERROR][0]
    assert event.get("culprit") == None
    assert event["log"]["message"] == "This is a test of no stacks"
    assert "stacktrace" not in event["log"]
    assert "exception" not in event
    assert "param_message" in event["log"]
    assert event["log"]["param_message"] == "This is a test of no stacks"


def test_no_record_stack_via_config(logger):
    logger.client.config.auto_log_stacks = False
    logger.info("This is a test of no stacks")
    assert len(logger.client.events) == 1
    event = logger.client.events[ERROR][0]
    assert event.get("culprit") == None
    assert event["log"]["message"] == "This is a test of no stacks"
    assert "stacktrace" not in event["log"]
    assert "exception" not in event
    assert "param_message" in event["log"]
    assert event["log"]["param_message"] == "This is a test of no stacks"


def test_explicit_stack(logger):
    logger.info("This is a test of stacks", extra={"stack": iter_stack_frames()})
    assert len(logger.client.events) == 1
    event = logger.client.events[ERROR][0]
    assert "culprit" in event, event
    assert event["culprit"] == "tests.handlers.logging.logging_tests.test_explicit_stack"
    assert "message" in event["log"], event
    assert event["log"]["message"] == "This is a test of stacks"
    assert "exception" not in event
    assert "param_message" in event["log"]
    assert event["log"]["param_message"] == "This is a test of stacks"
    assert "stacktrace" in event["log"]


def test_extra_culprit(logger):
    logger.info("This is a test of stacks", extra={"culprit": "foo.bar"})
    assert len(logger.client.events) == 1
    event = logger.client.events[ERROR][0]
    assert event["culprit"] == "foo.bar"
    assert "culprit" not in event["context"]["custom"]


def test_logger_exception(logger):
    try:
        raise ValueError("This is a test ValueError")
    except ValueError:
        logger.exception("This is a test with an exception", extra={"stack": True})

    assert len(logger.client.events) == 1
    event = logger.client.events[ERROR][0]

    assert event["log"]["message"] == "This is a test with an exception"
    assert "stacktrace" in event["log"]
    assert "exception" in event
    exc = event["exception"]
    assert exc["type"] == "ValueError"
    assert exc["message"] == "ValueError: This is a test ValueError"
    assert "param_message" in event["log"]
    assert event["log"]["message"] == "This is a test with an exception"


def test_client_arg(elasticapm_client):
    handler = LoggingHandler(elasticapm_client)
    assert handler.client == elasticapm_client


def test_client_kwarg(elasticapm_client):
    handler = LoggingHandler(client=elasticapm_client)
    assert handler.client == elasticapm_client


def test_logger_setup():
    handler = LoggingHandler(
        server_url="foo", service_name="bar", secret_token="baz", metrics_interval="0ms", client_cls=TempStoreClient
    )
    client = handler.client
    assert client.config.server_url == "foo"
    assert client.config.service_name == "bar"
    assert client.config.secret_token == "baz"
    assert handler.level == logging.NOTSET


def test_logging_handler_emit_error(capsys, elasticapm_client):
    handler = LoggingHandler(elasticapm_client)
    handler._emit = lambda: 1 / 0
    handler.emit(LogRecord("x", 1, "/ab/c/", 10, "Oops", [], None))
    out, err = capsys.readouterr()
    assert "Top level ElasticAPM exception caught" in err
    assert "Oops" in err


def test_logging_handler_dont_emit_elasticapm(capsys, elasticapm_client):
    handler = LoggingHandler(elasticapm_client)
    handler.emit(LogRecord("elasticapm.errors", 1, "/ab/c/", 10, "Oops", [], None))
    out, err = capsys.readouterr()
    assert "Oops" in err


def test_arbitrary_object(logger):
    logger.error(["a", "list", "of", "strings"])
    assert len(logger.client.events) == 1
    event = logger.client.events[ERROR][0]
    assert "param_message" in event["log"]
    assert event["log"]["param_message"] == "['a', 'list', 'of', 'strings']"


def test_logging_filter_no_span(elasticapm_client):
    transaction = elasticapm_client.begin_transaction("test")
    f = LoggingFilter()
    record = logging.LogRecord(__name__, logging.DEBUG, __file__, 252, "dummy_msg", [], None)
    f.filter(record)
    assert record.elasticapm_transaction_id == transaction.id
    assert record.elasticapm_trace_id == transaction.trace_parent.trace_id
    assert record.elasticapm_span_id is None
    assert record.elasticapm_labels


def test_structlog_processor_no_span(elasticapm_client):
    transaction = elasticapm_client.begin_transaction("test")
    event_dict = {}
    new_dict = structlog_processor(None, None, event_dict)
    assert new_dict["transaction.id"] == transaction.id
    assert new_dict["trace.id"] == transaction.trace_parent.trace_id
    assert "span.id" not in new_dict


@pytest.mark.parametrize("elasticapm_client", [{"transaction_max_spans": 5}], indirect=True)
def test_logging_filter_span(elasticapm_client):
    transaction = elasticapm_client.begin_transaction("test")
    with capture_span("test") as span:
        f = LoggingFilter()
        record = logging.LogRecord(__name__, logging.DEBUG, __file__, 252, "dummy_msg", [], None)
        f.filter(record)
        assert record.elasticapm_transaction_id == transaction.id
        assert record.elasticapm_trace_id == transaction.trace_parent.trace_id
        assert record.elasticapm_span_id == span.id
        assert record.elasticapm_labels

    # Capture too many spans so we start dropping
    for i in range(10):
        with capture_span("drop"):
            pass

    # Test logging with DroppedSpan
    with capture_span("drop") as span:
        record = logging.LogRecord(__name__, logging.DEBUG, __file__, 252, "dummy_msg2", [], None)
        f.filter(record)
        assert record.elasticapm_transaction_id == transaction.id
        assert record.elasticapm_trace_id == transaction.trace_parent.trace_id
        assert record.elasticapm_span_id is None
        assert record.elasticapm_labels


@pytest.mark.parametrize("elasticapm_client", [{"transaction_max_spans": 5}], indirect=True)
def test_structlog_processor_span(elasticapm_client):
    transaction = elasticapm_client.begin_transaction("test")
    with capture_span("test") as span:
        event_dict = {}
        new_dict = structlog_processor(None, None, event_dict)
        assert new_dict["transaction.id"] == transaction.id
        assert new_dict["trace.id"] == transaction.trace_parent.trace_id
        assert new_dict["span.id"] == span.id

    # Capture too many spans so we start dropping
    for i in range(10):
        with capture_span("drop"):
            pass

    # Test logging with DroppedSpan
    with capture_span("drop") as span:
        event_dict = {}
        new_dict = structlog_processor(None, None, event_dict)
        assert new_dict["transaction.id"] == transaction.id
        assert new_dict["trace.id"] == transaction.trace_parent.trace_id
        assert "span.id" not in new_dict


@pytest.mark.skipif(not compat.PY3, reason="Log record factories are only 3.2+")
def test_automatic_log_record_factory_install(elasticapm_client):
    """
    Use the elasticapm_client fixture to load the client, which in turn installs
    the log_record_factory. Check to make sure it happened.
    """
    transaction = elasticapm_client.begin_transaction("test")
    with capture_span("test") as span:
        record_factory = logging.getLogRecordFactory()
        record = record_factory(__name__, logging.DEBUG, __file__, 252, "dummy_msg", [], None)
        assert record.elasticapm_transaction_id == transaction.id
        assert record.elasticapm_trace_id == transaction.trace_parent.trace_id
        assert record.elasticapm_span_id == span.id
        assert record.elasticapm_labels


def test_formatter():
    record = logging.LogRecord(__name__, logging.DEBUG, __file__, 252, "dummy_msg", [], None)
    formatter = Formatter()
    formatted_record = formatter.format(record)
    assert "| elasticapm" in formatted_record
    assert hasattr(record, "elasticapm_transaction_id")
    record = logging.LogRecord(__name__, logging.DEBUG, __file__, 252, "dummy_msg", [], None)
    formatted_time = formatter.formatTime(record)
    assert formatted_time
    assert hasattr(record, "elasticapm_transaction_id")


def test_logging_handler_no_client(recwarn):
    # In 6.0, this should be changed to expect a ValueError instead of a log
    warnings.simplefilter("always")
    LoggingHandler()
    while True:
        # If we never find our desired warning this will eventually throw an
        # AssertionError
        w = recwarn.pop(PendingDeprecationWarning)
        if "LoggingHandler requires a Client instance" in w.message.args[0]:
            return True
