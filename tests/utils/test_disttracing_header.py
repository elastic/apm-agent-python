import pytest

from elasticapm.utils import compat
from elasticapm.utils.disttracing import parse_traceparent_header


@pytest.mark.parametrize(
    "tracing_bits,expected",
    [
        ("00", {"requested": 0, "recorded": 0}),
        ("01", {"requested": 1, "recorded": 0}),
        ("02", {"requested": 0, "recorded": 1}),
        ("03", {"requested": 1, "recorded": 1}),
    ],
)
def test_tracing_options(tracing_bits, expected):
    header = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-{}".format(tracing_bits)
    trace_parent = parse_traceparent_header(header)
    assert trace_parent.trace_options.requested == expected["requested"]
    assert trace_parent.trace_options.recorded == expected["recorded"]


def test_trace_parent_to_ascii():
    header = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03"
    trace_parent = parse_traceparent_header(header)
    result = trace_parent.to_ascii()
    assert isinstance(result, compat.binary_type)
    assert header.encode("ascii") == result
