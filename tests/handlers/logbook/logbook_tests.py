import logbook
import pytest
from logbook import LogRecord

from elasticapm.conf.constants import ERROR
from elasticapm.handlers.logbook import LogbookHandler


@pytest.fixture()
def logbook_logger():
    return logbook.Logger(__name__)


@pytest.fixture()
def logbook_handler(elasticapm_client):
    elasticapm_client.config.include_paths = ["tests", "elasticapm"]
    return LogbookHandler(elasticapm_client)


def test_logbook_logger_error_level(logbook_logger, logbook_handler):
    with logbook_handler.applicationbound():
        logbook_logger.error("This is a test error")

    assert len(logbook_handler.client.events) == 1
    event = logbook_handler.client.events[ERROR][0]
    assert event["log"]["logger_name"] == __name__
    assert event["log"]["level"] == "error"
    assert event["log"]["message"] == "This is a test error"
    assert "stacktrace" in event["log"]
    assert "exception" not in event
    assert "param_message" in event["log"]
    assert event["log"]["param_message"] == "This is a test error"


def test_logger_warning_level(logbook_logger, logbook_handler):
    with logbook_handler.applicationbound():
        logbook_logger.warning("This is a test warning")
    assert len(logbook_handler.client.events) == 1
    event = logbook_handler.client.events[ERROR][0]
    assert event["log"]["logger_name"] == __name__
    assert event["log"]["level"] == "warning"
    assert event["log"]["message"] == "This is a test warning"
    assert "stacktrace" in event["log"]
    assert "exception" not in event
    assert "param_message" in event["log"]
    assert event["log"]["param_message"] == "This is a test warning"


def test_logger_without_stacktrace_config(logbook_logger, logbook_handler):
    logbook_handler.client.config.auto_log_stacks = False

    with logbook_handler.applicationbound():
        logbook_logger.warning("This is a test warning")

    event = logbook_handler.client.events[ERROR][0]
    assert "stacktrace" not in event["log"]


def test_logger_without_stacktrace_stack_false(logbook_logger, logbook_handler):
    logbook_handler.client.config.auto_log_stacks = True

    with logbook_handler.applicationbound():
        logbook_logger.warning("This is a test warning", stack=False)

    event = logbook_handler.client.events[ERROR][0]
    assert "stacktrace" not in event["log"]


def test_logger_with_extra(logbook_logger, logbook_handler):
    with logbook_handler.applicationbound():
        logbook_logger.info("This is a test info with a url", extra=dict(url="http://example.com"))
    assert len(logbook_handler.client.events) == 1
    event = logbook_handler.client.events[ERROR][0]
    assert event["context"]["custom"]["url"] == "http://example.com"
    assert "stacktrace" in event["log"]
    assert "exception" not in event
    assert "param_message" in event["log"]
    assert event["log"]["param_message"] == "This is a test info with a url"


def test_logger_with_exc_info(logbook_logger, logbook_handler):
    with logbook_handler.applicationbound():
        try:
            raise ValueError("This is a test ValueError")
        except ValueError:
            logbook_logger.info("This is a test info with an exception", exc_info=True)

    assert len(logbook_handler.client.events) == 1
    event = logbook_handler.client.events[ERROR][0]

    assert event["log"]["message"] == "This is a test info with an exception"
    assert "stacktrace" in event["log"]
    assert "exception" in event
    exc = event["exception"]
    assert exc["type"] == "ValueError"
    assert exc["message"] == "ValueError: This is a test ValueError"
    assert "param_message" in event["log"]
    assert event["log"]["param_message"] == "This is a test info with an exception"


def test_logger_param_message(logbook_logger, logbook_handler):
    with logbook_handler.applicationbound():
        logbook_logger.info("This is a test of %s", "args")
    assert len(logbook_handler.client.events) == 1
    event = logbook_handler.client.events[ERROR][0]
    assert event["log"]["message"] == "This is a test of args"
    assert "stacktrace" in event["log"]
    assert "exception" not in event
    assert "param_message" in event["log"]
    assert event["log"]["param_message"] == "This is a test of %s"


def test_client_arg(elasticapm_client):
    handler = LogbookHandler(elasticapm_client)
    assert handler.client == elasticapm_client


def test_client_kwarg(elasticapm_client):
    handler = LogbookHandler(client=elasticapm_client)
    assert handler.client == elasticapm_client


def test_invalid_first_arg_type():
    with pytest.raises(ValueError):
        LogbookHandler(object)


def test_missing_client_arg():
    with pytest.raises(TypeError):
        LogbookHandler()


def test_logbook_handler_emit_error(capsys, elasticapm_client):
    handler = LogbookHandler(elasticapm_client)
    handler._emit = lambda: 1 / 0
    handler.emit(LogRecord("x", 1, "Oops"))
    out, err = capsys.readouterr()
    assert "Top level ElasticAPM exception caught" in err
    assert "Oops" in err


def test_logbook_handler_dont_emit_elasticapm(capsys, elasticapm_client):
    handler = LogbookHandler(elasticapm_client)
    handler.emit(LogRecord("elasticapm.errors", 1, "Oops"))
    out, err = capsys.readouterr()
    assert "Oops" in err
