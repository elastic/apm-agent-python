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


@pytest.mark.parametrize(
    "state_header",
    [
        "es=foo:bar;baz:qux,othervendor=<opaque>",
        "snes=x:y,es=foo:bar;baz:qux,othervendor=<opaque>",
        "othervendor=<opaque>,es=foo:bar;baz:qux",
    ],
)
def test_tracestate_parsing(state_header):
    header = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03"
    trace_parent = TraceParent.from_string(header, tracestate_string=state_header)
    assert trace_parent.tracestate == state_header
    assert trace_parent.tracestate_dict["foo"] == "bar"
    assert trace_parent.tracestate_dict["baz"] == "qux"
    assert len(trace_parent.tracestate_dict) == 2


@pytest.mark.parametrize("state_header", ["es=,othervendor=<opaque>", "foo=bar,baz=qux", ""])
def test_tracestate_parsing_empty(state_header):
    header = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03"
    trace_parent = TraceParent.from_string(header, tracestate_string=state_header)
    assert trace_parent.tracestate == state_header
    assert not trace_parent.tracestate_dict


def test_tracestate_adding_valid():
    header = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03"
    state_header = "es=foo:bar;baz:qux,othervendor=<opaque>"
    trace_parent = TraceParent.from_string(header, tracestate_string=state_header)
    trace_parent.add_tracestate("x", "y")
    assert trace_parent.tracestate_dict["x"] == "y"
    assert len(trace_parent.tracestate_dict) == 3
    trace_parent.add_tracestate("x", 1)
    assert trace_parent.tracestate_dict["x"] == "1"


@pytest.mark.parametrize("bad_char", ["\n", ":", ","])
def test_tracestate_adding_invalid(bad_char):
    header = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03"
    state_header = "es=foo:bar;baz:qux,othervendor=<opaque>"
    trace_parent = TraceParent.from_string(header, tracestate_string=state_header)
    trace_parent.add_tracestate("x", "y{}".format(bad_char))
    assert len(trace_parent.tracestate_dict) == 2
    assert "x" not in trace_parent.tracestate_dict
    trace_parent.add_tracestate("x{}".format(bad_char), "y")
    assert len(trace_parent.tracestate_dict) == 2
    assert "x{}".format(bad_char) not in trace_parent.tracestate_dict


def test_tracestate_length():
    header = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03"
    state_header = "es=foo:bar;baz:qux,othervendor=<opaque>"
    trace_parent = TraceParent.from_string(header, tracestate_string=state_header)
    trace_parent.add_tracestate("x", "y" * 256)
    assert len(trace_parent.tracestate_dict) == 2
    assert "x" not in trace_parent.tracestate_dict
