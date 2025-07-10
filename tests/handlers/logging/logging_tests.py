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
import logging.handlers
import sys
import warnings
from logging import LogRecord

import ecs_logging
import pytest
import structlog

from elasticapm.conf import Config
from elasticapm.conf.constants import ERROR
from elasticapm.handlers.logging import Formatter
from elasticapm.handlers.structlog import structlog_processor
from elasticapm.traces import capture_span
from elasticapm.utils.stacks import iter_stack_frames
from tests.fixtures import TempStoreClient


def test_structlog_processor_no_span(elasticapm_client):
    transaction = elasticapm_client.begin_transaction("test")
    event_dict = {}
    new_dict = structlog_processor(None, None, event_dict)
    assert new_dict["transaction.id"] == transaction.id
    assert new_dict["trace.id"] == transaction.trace_parent.trace_id
    assert "span.id" not in new_dict


@pytest.mark.parametrize("elasticapm_client", [{"transaction_max_spans": 5}], indirect=True)
def test_structlog_processor_span(elasticapm_client):
    transaction = elasticapm_client.begin_transaction("test")
    with capture_span("test") as span:
        event_dict = {}
        new_dict = structlog_processor(None, None, event_dict)
        assert new_dict["transaction.id"] == transaction.id
        assert new_dict["service.name"] == transaction.tracer.config.service_name
        assert new_dict["service.environment"] == transaction.tracer.config.environment
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
        assert new_dict["service.name"] == transaction.tracer.config.service_name
        assert new_dict["service.environment"] == transaction.tracer.config.environment
        assert new_dict["trace.id"] == transaction.trace_parent.trace_id
        assert "span.id" not in new_dict


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
        assert record.elasticapm_service_name == transaction.tracer.config.service_name
        assert record.elasticapm_service_environment == transaction.tracer.config.environment
        assert record.elasticapm_trace_id == transaction.trace_parent.trace_id
        assert record.elasticapm_span_id == span.id
        assert record.elasticapm_labels


def test_formatter():
    record = logging.LogRecord(__name__, logging.DEBUG, __file__, 252, "dummy_msg", [], None)
    formatter = Formatter()
    formatted_record = formatter.format(record)
    assert "| elasticapm" in formatted_record
    assert hasattr(record, "elasticapm_transaction_id")
    assert hasattr(record, "elasticapm_service_name")
    assert hasattr(record, "elasticapm_service_environment")
    record = logging.LogRecord(__name__, logging.DEBUG, __file__, 252, "dummy_msg", [], None)
    formatted_time = formatter.formatTime(record)
    assert formatted_time
    assert hasattr(record, "elasticapm_transaction_id")
    assert hasattr(record, "elasticapm_service_name")
    assert hasattr(record, "elasticapm_service_environment")


@pytest.mark.parametrize(
    "elasticapm_client,expected",
    [
        ({}, logging.NOTSET),
        ({"log_level": "off"}, 1000),
        ({"log_level": "trace"}, 5),
        ({"log_level": "debug"}, logging.DEBUG),
        ({"log_level": "info"}, logging.INFO),
        ({"log_level": "WARNING"}, logging.WARNING),
        ({"log_level": "errOr"}, logging.ERROR),
        ({"log_level": "CRITICAL"}, logging.CRITICAL),
    ],
    indirect=["elasticapm_client"],
)
def test_log_level_config(elasticapm_client, expected):
    logger = logging.getLogger("elasticapm")
    assert logger.level == expected


def test_log_file(elasticapm_client_log_file):
    logger = logging.getLogger("elasticapm")
    found = False
    for handler in logger.handlers:
        if isinstance(handler, logging.handlers.RotatingFileHandler):
            found = True
    assert found


@pytest.mark.parametrize("elasticapm_client_log_file", [{"log_ecs_reformatting": "override"}], indirect=True)
def test_log_ecs_reformatting(elasticapm_client_log_file):
    logger = logging.getLogger()
    assert isinstance(logger.handlers[0].formatter, ecs_logging.StdlibFormatter)
    assert isinstance(structlog.get_config()["processors"][-1], ecs_logging.StructlogFormatter)
