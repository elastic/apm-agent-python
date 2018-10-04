import pytest

from elasticapm.utils import compat
from elasticapm.utils.disttracing import TraceParent


@pytest.mark.parametrize("tracing_bits,expected", [("00", {"recorded": 0}), ("01", {"recorded": 1})])
def test_tracing_options(tracing_bits, expected):
    header = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-{}".format(tracing_bits)
    trace_parent = TraceParent.from_string(header)
    assert trace_parent.trace_options.recorded == expected["recorded"]


def test_trace_parent_to_ascii():
    header = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03"
    trace_parent = TraceParent.from_string(header)
    result = trace_parent.to_ascii()
    assert isinstance(result, compat.binary_type)
    assert header.encode("ascii") == result
