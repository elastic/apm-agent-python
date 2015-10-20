# -*- coding: utf-8 -*-

from opbeat.instrumentation.packages.base import AbstractInstrumentedModule


class TestInstrumentNonExistingFunctionOnModule(AbstractInstrumentedModule):
    name = "test_non_existing_function_instrumentation"
    instrument_list = [
        ("os.path", "non_existing_function")
    ]


class TestInstrumentNonExistingMethod(AbstractInstrumentedModule):
    name = "test_non_existing_method_instrumentation"
    instrument_list = [
        ("dict", "non_existing_method")
    ]


def test_instrument_nonexisting_method_on_module():
    TestInstrumentNonExistingFunctionOnModule().instrument()


def test_instrument_nonexisting_method():
    TestInstrumentNonExistingMethod().instrument()
