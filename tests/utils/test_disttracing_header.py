import pytest

from elasticapm.utils import compat
from elasticapm.utils.disttracing import TraceParent


@pytest.mark.parametrize("tracing_bits,expected", [("00", {"recorded": 0}), ("01", {"recorded": 1})])
def test_tracing_options(tracing_bits, expected):
    header = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-{}".format(tracing_bits)
    trace_parent = TraceParent.from_string(header)
    assert trace_parent.trace_options.recorded == expected["recorded"]


def test_unknown_header_components_ignored():
    header = "01-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03-xyz"
    trace_parent = TraceParent.from_string(header)
    assert trace_parent.to_ascii().decode("ascii") == "01-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03"


def test_trace_parent_to_ascii():
    header = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03"
    trace_parent = TraceParent.from_string(header)
    result = trace_parent.to_ascii()
    assert isinstance(result, compat.binary_type)
    assert header.encode("ascii") == result


def test_trace_parent_wrong_version(caplog):
    header = "xx-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03"
    with caplog.at_level("DEBUG", "elasticapm.utils"):
        trace_parent = TraceParent.from_string(header)
    record = caplog.records[0]
    assert trace_parent is None
    assert record.message == "Invalid version field, value xx"


def test_trace_parent_wrong_version_255(caplog):
    """Version FF or 255 is explicitly forbidden"""
    header = "ff-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03"
    with caplog.at_level("DEBUG", "elasticapm.utils"):
        trace_parent = TraceParent.from_string(header)
    record = caplog.records[0]
    assert trace_parent is None
    assert record.message == "Invalid version field, value ff"


def test_trace_parent_wrong_trace_options_field(caplog):
    header = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-xx"
    with caplog.at_level("DEBUG", "elasticapm.utils"):
        trace_parent = TraceParent.from_string(header)
    record = caplog.records[0]
    assert trace_parent is None
    assert record.message == "Invalid trace-options field, value xx"


def test_trace_parent_wrong_format(caplog):
    header = "00"
    with caplog.at_level("DEBUG", "elasticapm.utils"):
        trace_parent = TraceParent.from_string(header)
    record = caplog.records[0]
    assert trace_parent is None
    assert record.message == "Invalid traceparent header format, value 00"
