# -*- coding: utf-8 -*-
import logging
import types

import mock
import pytest

import elasticapm
from elasticapm.conf.constants import SPAN
from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.utils import compat, wrapt


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
        return wrapped(*args, **kwargs)


def test_instrument_nonexisting_method_on_module():
    _TestInstrumentNonExistingFunctionOnModule().instrument()


def test_instrument_nonexisting_method(caplog):
    with caplog.at_level(logging.DEBUG, "elasticapm.instrument"):
        _TestInstrumentNonExistingMethod().instrument()
    record = caplog.records[0]
    assert "has no attribute" in record.message


@pytest.mark.skipif(compat.PY3, reason="different object model")
def test_uninstrument_py2(caplog):
    assert isinstance(Dummy.dummy, types.MethodType)
    assert not isinstance(Dummy.dummy, wrapt.BoundFunctionWrapper)

    instrumentation = _TestDummyInstrumentation()
    with caplog.at_level(logging.DEBUG, "elasticapm.instrument"):
        instrumentation.instrument()
    record = caplog.records[0]
    assert "Instrumented" in record.message
    assert record.args == ("test_dummy_instrument", "tests.instrumentation.base_tests.Dummy.dummy")
    assert isinstance(Dummy.dummy, wrapt.BoundFunctionWrapper)

    with caplog.at_level(logging.DEBUG, "elasticapm.instrument"):
        instrumentation.uninstrument()
    record = caplog.records[1]
    assert "Uninstrumented" in record.message
    assert record.args == ("test_dummy_instrument", "tests.instrumentation.base_tests.Dummy.dummy")
    assert isinstance(Dummy.dummy, types.MethodType)
    assert not isinstance(Dummy.dummy, wrapt.BoundFunctionWrapper)


@pytest.mark.skipif(compat.PY2, reason="different object model")
def test_uninstrument_py3(caplog):
    original = Dummy.dummy
    assert not isinstance(Dummy.dummy, wrapt.BoundFunctionWrapper)

    instrumentation = _TestDummyInstrumentation()
    with caplog.at_level(logging.DEBUG, "elasticapm.instrument"):
        instrumentation.instrument()
    record = caplog.records[0]
    assert "Instrumented" in record.message
    assert record.args == ("test_dummy_instrument", "tests.instrumentation.base_tests.Dummy.dummy")
    assert Dummy.dummy is not original
    assert isinstance(Dummy.dummy, wrapt.BoundFunctionWrapper)

    with caplog.at_level(logging.DEBUG, "elasticapm.instrument"):
        instrumentation.uninstrument()
    record = caplog.records[1]
    assert "Uninstrumented" in record.message
    assert record.args == ("test_dummy_instrument", "tests.instrumentation.base_tests.Dummy.dummy")
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
    record = caplog.records[0]
    assert "Skipping" in record.message
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
    with caplog.at_level(logging.INFO):
        t = elasticapm_client.begin_transaction("test")
        # we're purposefully creating a case where we don't begin a span
        # and then try to end the non-existing span
        t.is_sampled = False
        with elasticapm.capture_span("test_name", "test_type"):
            t.is_sampled = True
    elasticapm_client.end_transaction("test", "")
    record = caplog.records[0]
    assert record.args == ("test_name", "test_type")
