# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import pkgutil

import pytest
from mock import Mock

from elasticapm.utils import compat, stacks
from elasticapm.utils.stacks import get_culprit, get_stack_info
from tests.utils.stacks import get_me_a_test_frame


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
    frames = [
        Mock(f_lineno=1, f_globals={}),
        Mock(f_lineno=2, f_globals={}),
        Mock(f_lineno=3, f_globals={}),
        Mock(f_lineno=4, f_globals={}),
    ]

    iterated_frames = list(stacks.iter_stack_frames(frames, skip=3))
    assert len(iterated_frames) == 1
    assert iterated_frames[0][1] == 4


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
    assert frame_info["lineno"] == 6
    assert frame_info["context_line"] == "    return inspect.currentframe()"
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
