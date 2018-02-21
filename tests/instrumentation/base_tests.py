# -*- coding: utf-8 -*-
import types

import mock
import pytest

import elasticapm
from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.utils import compat, wrapt


class Dummy(object):
    def dummy(self, call_args=None):
        return call_args


class _TestInstrumentNonExistingFunctionOnModule(AbstractInstrumentedModule):
    name = "test_non_existing_function_instrumentation"
    instrument_list = [
        ("os.path", "non_existing_function"),
    ]


class _TestInstrumentNonExistingMethod(AbstractInstrumentedModule):
    name = "test_non_existing_method_instrumentation"
    instrument_list = [
        ("dict", "non_existing_method"),
    ]


class _TestDummyInstrumentation(AbstractInstrumentedModule):
    name = "test_dummy_instrument"

    instrument_list = [
        ("tests.instrumentation.base_tests", "Dummy.dummy"),
    ]

    def call(self, module, method, wrapped, instance, args, kwargs):
        kwargs = kwargs or {}
        kwargs['call_args'] = (module, method)
        return wrapped(*args, **kwargs)



def test_instrument_nonexisting_method_on_module():
    _TestInstrumentNonExistingFunctionOnModule().instrument()


def test_instrument_nonexisting_method():
    _TestInstrumentNonExistingMethod().instrument()


@pytest.mark.skipif(compat.PY3, reason="different object model")
def test_uninstrument_py2():
    assert isinstance(Dummy.dummy, types.MethodType)
    assert not isinstance(Dummy.dummy, wrapt.BoundFunctionWrapper)

    instrumentation = _TestDummyInstrumentation()
    instrumentation.instrument()
    assert isinstance(Dummy.dummy, wrapt.BoundFunctionWrapper)

    instrumentation.uninstrument()
    assert isinstance(Dummy.dummy, types.MethodType)
    assert not isinstance(Dummy.dummy, wrapt.BoundFunctionWrapper)


@pytest.mark.skipif(compat.PY2, reason="different object model")
def test_uninstrument_py3():
    original = Dummy.dummy
    assert not isinstance(Dummy.dummy, wrapt.BoundFunctionWrapper)

    instrumentation = _TestDummyInstrumentation()
    instrumentation.instrument()

    assert Dummy.dummy is not original
    assert isinstance(Dummy.dummy, wrapt.BoundFunctionWrapper)

    instrumentation.uninstrument()
    assert Dummy.dummy is original
    assert not isinstance(Dummy.dummy, wrapt.BoundFunctionWrapper)


def test_module_method_args(elasticapm_client):
    """
    Test that the module/method arguments are correctly passed to
    the _TestDummyInstrumentation.call method
    """
    instrumentation = _TestDummyInstrumentation()
    instrumentation.instrument()
    elasticapm_client.begin_transaction('test')
    dummy = Dummy()
    call_args = dummy.dummy()
    elasticapm_client.end_transaction('test', 'test')
    instrumentation.uninstrument()

    assert call_args == ('tests.instrumentation.base_tests', 'Dummy.dummy')


def test_skip_instrument_env_var():
    instrumentation = _TestDummyInstrumentation()
    with mock.patch.dict('os.environ', {'SKIP_INSTRUMENT_TEST_DUMMY_INSTRUMENT': 'foo'}):
        instrumentation.instrument()
    assert not instrumentation.instrumented


def test_skip_ignored_frames(elasticapm_client):
    elasticapm_client.begin_transaction('test')
    with elasticapm.capture_span('test'):
        pass
    transaction = elasticapm_client.end_transaction('test', 'test')
    for frame in transaction.spans[0].frames:
        assert not frame['module'].startswith('elasticapm')
