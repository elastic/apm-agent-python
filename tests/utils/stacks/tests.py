# -*- coding: utf-8 -*-

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

import os
import pkgutil

import pytest
from mock import Mock

import elasticapm
from elasticapm.conf import constants
from elasticapm.utils import compat, stacks
from elasticapm.utils.stacks import get_culprit, get_stack_info
from tests.utils.stacks import get_me_a_test_frame, get_me_more_test_frames


def nested_frames(count=10):
    if count == 0:
        return


class Context(object):
    def __init__(self, dict):
        self.dict = dict

    __getitem__ = lambda s, *a: s.dict.__getitem__(*a)
    __setitem__ = lambda s, *a: s.dict.__setitem__(*a)
    iterkeys = lambda s, *a: compat.iterkeys(s.dict, *a)


def test_get_culprit_bad_module():
    culprit = get_culprit([{"module": None, "function": "foo"}])
    assert culprit == "<unknown>.foo"

    culprit = get_culprit([{"module": "foo", "function": None}])
    assert culprit == "foo.<unknown>"

    culprit = get_culprit([{}])
    assert culprit == "<unknown>.<unknown>"


def test_bad_locals_in_frame():
    frame = Mock()
    frame.f_locals = Context({"foo": "bar", "biz": "baz"})
    frame.f_lineno = 1
    frame.f_globals = {}
    frame.f_code.co_filename = __file__.replace(".pyc", ".py")
    frame.f_code.co_name = __name__
    frames = [(frame, 1)]
    results = get_stack_info(frames)
    assert len(results) == 1
    result = results[0]
    assert "vars" in result
    variables = {"foo": "bar", "biz": "baz"}
    assert result["vars"] == variables


def test_traceback_hide(elasticapm_client):
    def get_me_a_filtered_frame(hide=True):
        __traceback_hide__ = True
        if not hide:
            del __traceback_hide__

        return list(stacks.iter_stack_frames())

    # hide frame from `get_me_a_filtered_frame
    frames = list(stacks.get_stack_info(get_me_a_filtered_frame(hide=True)))
    assert frames[0]["function"] == "test_traceback_hide"

    # don't hide it:
    frames = list(stacks.get_stack_info(get_me_a_filtered_frame(hide=False)))
    assert frames[0]["function"] == "get_me_a_filtered_frame"


def test_iter_stack_frames_skip_frames():
    frames = get_me_more_test_frames(4)

    iterated_frames = list(stacks.iter_stack_frames(frames, skip=3))
    assert len(iterated_frames) == 1
    assert iterated_frames[0][0].f_locals["count"] == 4


def test_iter_stack_frames_skip_frames_by_module():
    frames = [
        Mock(f_lineno=1, f_globals={"__name__": "foo.bar"}),
        Mock(f_lineno=2, f_globals={"__name__": "foo.bar"}),
        Mock(f_lineno=3, f_globals={"__name__": "baz.bar"}),
        Mock(f_lineno=4, f_globals={"__name__": "foo.bar"}),
    ]

    iterated_frames = list(stacks.iter_stack_frames(frames, skip_top_modules=("foo.",)))
    assert len(iterated_frames) == 2
    assert iterated_frames[0][1] == 3
    assert iterated_frames[1][1] == 4


def test_iter_stack_frames_max_frames():
    iterated_frames = list(stacks.iter_stack_frames(get_me_more_test_frames(10), config=Mock(stack_trace_limit=5)))
    assert len(iterated_frames) == 5
    assert iterated_frames[4][0].f_locals["count"] == 5

    iterated_frames = list(stacks.iter_stack_frames(get_me_more_test_frames(10), config=Mock(stack_trace_limit=-1)))
    assert len(iterated_frames) == 10

    iterated_frames = list(stacks.iter_stack_frames(get_me_more_test_frames(10), config=Mock(stack_trace_limit=0)))
    assert len(iterated_frames) == 0

    iterated_frames = list(
        stacks.iter_stack_frames(get_me_more_test_frames(10), skip=3, config=Mock(stack_trace_limit=5))
    )
    assert len(iterated_frames) == 5
    assert iterated_frames[4][0].f_locals["count"] == 8


@pytest.mark.parametrize(
    "elasticapm_client", [{"stack_trace_limit": 10, "span_frames_min_duration": -1}], indirect=True
)
def test_iter_stack_frames_max_frames_is_dynamic(elasticapm_client):
    def func():
        with elasticapm.capture_span("yay"):
            pass

    elasticapm_client.begin_transaction("foo")
    get_me_more_test_frames(15, func=func)
    elasticapm_client.end_transaction()
    transaction = elasticapm_client.events[constants.TRANSACTION][0]

    span = elasticapm_client.spans_for_transaction(transaction)[0]
    assert len(span["stacktrace"]) == 10

    elasticapm_client.config.update(version="2", stack_trace_limit=5)

    elasticapm_client.begin_transaction("foo")
    get_me_more_test_frames(15, func=func)
    elasticapm_client.end_transaction()
    transaction = elasticapm_client.events[constants.TRANSACTION][1]

    span = elasticapm_client.spans_for_transaction(transaction)[0]
    assert len(span["stacktrace"]) == 5


@pytest.mark.parametrize(
    "elasticapm_client", [{"include_paths": ("/a/b/c/*", "/c/d/*"), "exclude_paths": ("/c/*",)}], indirect=True
)
def test_library_frames(elasticapm_client):
    include = elasticapm_client.include_paths_re
    exclude = elasticapm_client.exclude_paths_re
    frame1 = Mock(f_code=Mock(co_filename="/a/b/c/d.py"))
    frame2 = Mock(f_code=Mock(co_filename="/a/b/c/d/e.py"))
    frame3 = Mock(f_code=Mock(co_filename="/c/d/e.py"))
    frame4 = Mock(f_code=Mock(co_filename="/c/e.py"))

    info1 = stacks.get_frame_info(frame1, 1, False, False, include_paths_re=include, exclude_paths_re=exclude)
    info2 = stacks.get_frame_info(frame2, 1, False, False, include_paths_re=include, exclude_paths_re=exclude)
    info3 = stacks.get_frame_info(frame3, 1, False, False, include_paths_re=include, exclude_paths_re=exclude)
    info4 = stacks.get_frame_info(frame4, 1, False, False, include_paths_re=include, exclude_paths_re=exclude)
    assert not info1["library_frame"]
    assert not info2["library_frame"]
    assert not info3["library_frame"]
    assert info4["library_frame"]


def test_get_frame_info():
    frame = get_me_a_test_frame()
    frame_info = stacks.get_frame_info(
        frame, frame.f_lineno, library_frame_context_lines=5, in_app_frame_context_lines=5, with_locals=True
    )
    assert frame_info["function"] == "get_me_a_test_frame"
    assert frame_info["filename"] == os.path.join("tests", "utils", "stacks", "__init__.py")
    assert frame_info["module"] == "tests.utils.stacks"
    assert frame_info["lineno"] == 36
    assert frame_info["context_metadata"][0].endswith(frame_info["filename"])
    assert frame_info["context_metadata"][1] == frame_info["lineno"]
    assert frame_info["context_metadata"][4] == frame_info["module"]
    assert frame_info["vars"] == {"a_local_var": 42}


@pytest.mark.parametrize(
    "lineno,context,expected",
    [
        (10, 5, (["5", "6", "7", "8", "9"], "10", ["11", "12", "13", "14", "15"])),
        (1, 5, ([], "1", ["2", "3", "4", "5", "6"])),
        (2, 5, (["1"], "2", ["3", "4", "5", "6", "7"])),
        (20, 5, (["15", "16", "17", "18", "19"], "20", [])),
        (19, 5, (["14", "15", "16", "17", "18"], "19", ["20"])),
        (1, 0, ([], "1", [])),
        (21, 0, (None, None, None)),
    ],
)
def test_get_lines_from_file(lineno, context, expected):
    stacks.get_lines_from_file.cache_clear()
    fname = os.path.join(os.path.dirname(__file__), "linenos.py")
    result = stacks.get_lines_from_file(fname, lineno, context)
    assert result == expected


@pytest.mark.parametrize(
    "lineno,context,expected",
    [
        (10, 5, (["5", "6", "7", "8", "9"], "10", ["11", "12", "13", "14", "15"])),
        (1, 5, ([], "1", ["2", "3", "4", "5", "6"])),
        (2, 5, (["1"], "2", ["3", "4", "5", "6", "7"])),
        (20, 5, (["15", "16", "17", "18", "19"], "20", [])),
        (19, 5, (["14", "15", "16", "17", "18"], "19", ["20"])),
        (1, 0, ([], "1", [])),
        (21, 0, (None, None, None)),
    ],
)
def test_get_lines_from_loader(lineno, context, expected):
    stacks.get_lines_from_file.cache_clear()
    module = "tests.utils.stacks.linenos"
    loader = pkgutil.get_loader(module)
    fname = os.path.join(os.path.dirname(__file__), "linenos.py")
    result = stacks.get_lines_from_file(fname, lineno, context, loader=loader, module_name=module)
    assert result == expected
