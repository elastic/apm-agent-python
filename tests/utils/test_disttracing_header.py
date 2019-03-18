from __future__ import absolute_import

import pytest

from elasticapm.utils.disttracing import TraceParent
from tests.utils import assert_any_record_contains


@pytest.mark.parametrize("tracing_bits,expected", [("00", {"recorded": 0}), ("01", {"recorded": 1})])
def test_tracing_options(tracing_bits, expected):
    header = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-{}".format(tracing_bits)
    trace_parent = TraceParent.from_string(header)
    assert trace_parent.trace_options.recorded == expected["recorded"]


def test_unknown_header_components_ignored():
    header = "01-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03-xyz"
    trace_parent = TraceParent.from_string(header)
    assert trace_parent.to_string() == "01-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03"


def test_trace_parent_to_str():
    header = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03"
    trace_parent = TraceParent.from_string(header)
    result = trace_parent.to_string()
    assert isinstance(result, str)
    assert header == result


def test_trace_parent_wrong_version(caplog):
    header = "xx-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03"
    with caplog.at_level("DEBUG", "elasticapm.utils"):
        trace_parent = TraceParent.from_string(header)
    assert trace_parent is None
    assert_any_record_contains(caplog.records, "Invalid version field, value xx")


def test_trace_parent_wrong_version_255(caplog):
    """Version FF or 255 is explicitly forbidden"""
    header = "ff-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03"
    with caplog.at_level("DEBUG", "elasticapm.utils"):
        trace_parent = TraceParent.from_string(header)
    assert trace_parent is None
    assert_any_record_contains(caplog.records, "Invalid version field, value 255")


def test_trace_parent_wrong_trace_options_field(caplog):
    header = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-xx"
    with caplog.at_level("DEBUG", "elasticapm.utils"):
        trace_parent = TraceParent.from_string(header)
    assert trace_parent is None
    assert_any_record_contains(caplog.records, "Invalid trace-options field, value xx")


def test_trace_parent_wrong_format(caplog):
    header = "00"
    with caplog.at_level("DEBUG", "elasticapm.utils"):
        trace_parent = TraceParent.from_string(header)
    assert trace_parent is None
    assert_any_record_contains(caplog.records, "Invalid traceparent header format, value 00")
