# -*- coding: utf-8 -*-

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

import mock
import pytest
import wrapt

import elasticapm
from elasticapm.conf import constants
from elasticapm.conf.constants import SPAN, TRANSACTION
from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from tests.utils import assert_any_record_contains


class Dummy(object):
    def dummy(self, call_args=None):
        return call_args


class _TestInstrumentNonExistingFunctionOnModule(AbstractInstrumentedModule):
    name = "test_non_existing_function_instrumentation"
    instrument_list = [("os.path", "non_existing_function")]


class _TestInstrumentNonExistingMethod(AbstractInstrumentedModule):
    name = "test_non_existing_method_instrumentation"
    instrument_list = [("logging", "Logger.non_existing_method")]


class _TestDummyInstrumentation(AbstractInstrumentedModule):
    name = "test_dummy_instrument"

    instrument_list = [("tests.instrumentation.base_tests", "Dummy.dummy")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        kwargs = kwargs or {}
        kwargs["call_args"] = (module, method)
        with elasticapm.capture_span("dummy"):
            return wrapped(*args, **kwargs)


def test_instrument_nonexisting_method_on_module():
    _TestInstrumentNonExistingFunctionOnModule().instrument()


def test_instrument_nonexisting_method(caplog):
    with caplog.at_level(logging.DEBUG, "elasticapm.instrument"):
        _TestInstrumentNonExistingMethod().instrument()
    assert_any_record_contains(caplog.records, "has no attribute", "elasticapm.instrument")


def test_double_instrument(elasticapm_client):
    elasticapm_client.begin_transaction("test")
    inst = _TestDummyInstrumentation()
    try:
        inst.instrument()
        assert hasattr(Dummy.dummy, "_self_wrapper")
        Dummy().dummy()
        elasticapm_client.end_transaction()
        assert len(elasticapm_client.spans_for_transaction(elasticapm_client.events[constants.TRANSACTION][0])) == 1
        inst.instrumented = False
        inst.instrument()
        elasticapm_client.begin_transaction("test")
        Dummy().dummy()
        elasticapm_client.end_transaction()
        assert len(elasticapm_client.spans_for_transaction(elasticapm_client.events[constants.TRANSACTION][1])) == 1
    finally:
        inst.uninstrument()


def test_uninstrument(caplog):
    original = Dummy.dummy
    assert not isinstance(Dummy.dummy, wrapt.BoundFunctionWrapper)

    instrumentation = _TestDummyInstrumentation()
    with caplog.at_level(logging.DEBUG, "elasticapm.instrument"):
        instrumentation.instrument()
    assert_any_record_contains(
        caplog.records,
        "Instrumented test_dummy_instrument, tests.instrumentation.base_tests.Dummy.dummy",
        "elasticapm.instrument",
    )
    assert Dummy.dummy is not original
    assert isinstance(Dummy.dummy, wrapt.BoundFunctionWrapper)

    with caplog.at_level(logging.DEBUG, "elasticapm.instrument"):
        instrumentation.uninstrument()
    assert_any_record_contains(
        caplog.records,
        "Uninstrumented test_dummy_instrument, tests.instrumentation.base_tests.Dummy.dummy",
        "elasticapm.instrument",
    )
    assert Dummy.dummy is original
    assert not isinstance(Dummy.dummy, wrapt.BoundFunctionWrapper)


def test_module_method_args(elasticapm_client):
    """
    Test that the module/method arguments are correctly passed to
    the _TestDummyInstrumentation.call method
    """
    instrumentation = _TestDummyInstrumentation()
    instrumentation.instrument()
    elasticapm_client.begin_transaction("test")
    dummy = Dummy()
    call_args = dummy.dummy()
    elasticapm_client.end_transaction("test", "test")
    instrumentation.uninstrument()

    assert call_args == ("tests.instrumentation.base_tests", "Dummy.dummy")


def test_skip_instrument_env_var(caplog):
    instrumentation = _TestDummyInstrumentation()
    with mock.patch.dict("os.environ", {"SKIP_INSTRUMENT_TEST_DUMMY_INSTRUMENT": "foo"}), caplog.at_level(
        logging.DEBUG, "elasticapm.instrument"
    ):
        instrumentation.instrument()
    assert_any_record_contains(caplog.records, "Skipping", "elasticapm.instrument")
    assert not instrumentation.instrumented


def test_skip_ignored_frames(elasticapm_client):
    elasticapm_client.begin_transaction("test")
    with elasticapm.capture_span("test"):
        pass
    elasticapm_client.end_transaction("test", "test")
    span = elasticapm_client.events[SPAN][0]
    for frame in span["stacktrace"]:
        assert not frame["module"].startswith("elasticapm")


def test_end_nonexisting_span(caplog, elasticapm_client):
    with caplog.at_level(logging.DEBUG, "elasticapm.traces"):
        t = elasticapm_client.begin_transaction("test")
        # we're purposefully creating a case where we don't begin a span
        # and then try to end the non-existing span
        t.is_sampled = False
        with elasticapm.capture_span("test_name", "test_type"):
            t.is_sampled = True
    elasticapm_client.end_transaction("test", "")
    assert_any_record_contains(
        caplog.records, "ended non-existing span test_name of type test_type", "elasticapm.traces"
    )


def test_outcome_by_span_exception(elasticapm_client):
    elasticapm_client.begin_transaction("test")
    try:
        with elasticapm.capture_span("fail", "test_type"):
            assert False
    except AssertionError:
        pass
    with elasticapm.capture_span("success", "test_type"):
        pass
    elasticapm_client.end_transaction("test")
    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])
    assert spans[0]["name"] == "fail" and spans[0]["outcome"] == "failure"
    assert spans[1]["name"] == "success" and spans[1]["outcome"] == "success"


@pytest.mark.parametrize(
    "outcome,http_status_code,log_message,result",
    [
        (None, 200, None, "success"),
        (None, 500, None, "failure"),
        (None, "500", None, "failure"),
        (None, "HTTP 500", "Invalid HTTP status 'HTTP 500' provided", "unknown"),
        ("failure", 200, None, "failure"),  # explicit outcome has precedence
        ("failed", None, "Invalid outcome 'failed' provided", "unknown"),
    ],
)
def test_transaction_outcome(elasticapm_client, caplog, outcome, http_status_code, log_message, result):
    transaction = elasticapm_client.begin_transaction("test")
    with caplog.at_level(logging.INFO, "elasticapm.traces"):
        elasticapm.set_transaction_outcome(outcome=outcome, http_status_code=http_status_code)
    assert transaction.outcome == result
    if log_message is None:
        assert not [True for record in caplog.records if record.name == "elasticapm.traces"]
    else:
        assert_any_record_contains(caplog.records, log_message, "elasticapm.traces")


def test_transaction_outcome_override(elasticapm_client):
    transaction = elasticapm_client.begin_transaction("test")
    elasticapm.set_transaction_outcome(constants.OUTCOME.FAILURE)

    assert transaction.outcome == constants.OUTCOME.FAILURE

    elasticapm.set_transaction_outcome(constants.OUTCOME.SUCCESS, override=False)
    # still a failure
    assert transaction.outcome == constants.OUTCOME.FAILURE

    elasticapm.set_transaction_outcome(constants.OUTCOME.SUCCESS, override=True)
    assert transaction.outcome == constants.OUTCOME.SUCCESS
