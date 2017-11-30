# -*- coding: utf-8 -*-
from __future__ import absolute_import

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
    culprit = get_culprit([{
        'module': None,
        'function': 'foo',
    }])
    assert culprit == '<unknown>.foo'

    culprit = get_culprit([{
        'module': 'foo',
        'function': None,
    }])
    assert culprit == 'foo.<unknown>'

    culprit = get_culprit([{
    }])
    assert culprit == '<unknown>.<unknown>'


def test_bad_locals_in_frame():
    frame = Mock()
    frame.f_locals = Context({
        'foo': 'bar',
        'biz': 'baz',
    })
    frame.f_lineno = 1
    frame.f_globals = {}
    frame.f_code.co_filename = __file__.replace('.pyc', '.py')
    frame.f_code.co_name = __name__
    frames = [(frame, 1)]
    results = get_stack_info(frames)
    assert len(results) == 1
    result = results[0]
    assert 'vars' in result
    variables = {
        "foo": "bar",
        "biz": "baz",
    }
    assert result['vars'] == variables


def test_traceback_hide(elasticapm_client):
    def get_me_a_filtered_frame(hide=True):
        __traceback_hide__ = True
        if not hide:
            del __traceback_hide__

        return list(stacks.iter_stack_frames())

    # hide frame from `get_me_a_filtered_frame
    frames = list(stacks.get_stack_info(get_me_a_filtered_frame(hide=True)))
    assert frames[0]['function'] == 'test_traceback_hide'

    # don't hide it:
    frames = list(stacks.get_stack_info(get_me_a_filtered_frame(hide=False)))
    assert frames[0]['function'] == 'get_me_a_filtered_frame'


def test_get_frame_info():
    frame = get_me_a_test_frame()
    frame_info = stacks.get_frame_info(frame, frame.f_lineno, extended=True)

    assert frame_info['function'] == 'get_me_a_test_frame'
    assert frame_info['filename'] == 'tests/utils/stacks/__init__.py'
    assert frame_info['module'] == 'tests.utils.stacks'
    assert frame_info['lineno'] == 6
    assert frame_info['context_line'] == '    return inspect.currentframe()'
    assert frame_info['vars'] == {'a_local_var': 42}
