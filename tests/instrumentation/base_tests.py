# -*- coding: utf-8 -*-
import types

import pytest

from elasticapm.instrumentation.packages.base import (AbstractInstrumentedModule,
                                                      OriginalNamesBoundFunctionWrapper)
from elasticapm.utils import compat


class Dummy(object):
    def dummy(self):
        pass


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


def test_instrument_nonexisting_method_on_module():
    _TestInstrumentNonExistingFunctionOnModule().instrument()


def test_instrument_nonexisting_method():
    _TestInstrumentNonExistingMethod().instrument()


@pytest.mark.skipif(compat.PY3, reason="different object model")
def test_uninstrument_py2():
    assert isinstance(Dummy.dummy, types.MethodType)
    assert not isinstance(Dummy.dummy, OriginalNamesBoundFunctionWrapper)

    instrumentation = _TestDummyInstrumentation()
    instrumentation.instrument()
    assert isinstance(Dummy.dummy, OriginalNamesBoundFunctionWrapper)

    instrumentation.uninstrument()
    assert isinstance(Dummy.dummy, types.MethodType)
    assert not isinstance(Dummy.dummy, OriginalNamesBoundFunctionWrapper)


@pytest.mark.skipif(compat.PY2, reason="different object model")
def test_uninstrument_py3():
    original = Dummy.dummy
    assert not isinstance(Dummy.dummy, OriginalNamesBoundFunctionWrapper)

    instrumentation = _TestDummyInstrumentation()
    instrumentation.instrument()

    assert Dummy.dummy is not original
    assert isinstance(Dummy.dummy, OriginalNamesBoundFunctionWrapper)

    instrumentation.uninstrument()
    assert Dummy.dummy is original
    assert not isinstance(Dummy.dummy, OriginalNamesBoundFunctionWrapper)
