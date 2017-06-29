# -*- coding: utf-8 -*-

from opbeat.instrumentation.packages.base import AbstractInstrumentedModule


class _TestInstrumentNonExistingFunctionOnModule(AbstractInstrumentedModule):
    name = "test_non_existing_function_instrumentation"
    instrument_list = [
        ("os.path", "non_existing_function")
    ]


class _TestInstrumentNonExistingMethod(AbstractInstrumentedModule):
    name = "test_non_existing_method_instrumentation"
    instrument_list = [
        ("dict", "non_existing_method")
    ]


def test_instrument_nonexisting_method_on_module():
    _TestInstrumentNonExistingFunctionOnModule().instrument()


def test_instrument_nonexisting_method():
    _TestInstrumentNonExistingMethod().instrument()
