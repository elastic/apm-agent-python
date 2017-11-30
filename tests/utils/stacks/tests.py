# -*- coding: utf-8 -*-
from __future__ import absolute_import

import pytest
from mock import Mock

from elasticapm.utils import compat, stacks
from tests.utils.stacks import get_me_a_test_frame


class Context(object):
    def __init__(self, dict):
        self.dict = dict

    __getitem__ = lambda s, *a: s.dict.__getitem__(*a)
    __setitem__ = lambda s, *a: s.dict.__setitem__(*a)
    iterkeys = lambda s, *a: compat.iterkeys(s.dict, *a)


def test_get_culprit_bad_module():
    culprit = stacks.get_culprit([{
        'module': None,
        'function': 'foo',
    }])
    assert culprit == '<unknown>.foo'

    culprit = stacks.get_culprit([{
        'module': 'foo',
        'function': None,
    }])
    assert culprit == 'foo.<unknown>'

    culprit = stacks.get_culprit([{
    }])
    assert culprit == '<unknown>.<unknown>'



def test_bad_locals_in_frame(elasticapm_client):
    frame = Mock()
    frame.f_locals = Context({
        'foo': 'bar',
        'biz': 'baz',
    })
    frame.f_lineno = 1
    frame.f_globals = {}
    frame.f_code.co_filename = __file__.replace('.pyc', '.py')
    frame.f_code.co_name = __name__
    frames = [(frame, 1, True)]
    results = list(stacks.get_stack_info(elasticapm_client, frames))
    assert len(results) == 1
    result = results[0]
    assert 'vars' in result
    vars = {
        "foo": "bar",
        "biz": "baz",
    }
    assert result['vars'] == vars


@pytest.mark.parametrize('elasticapm_client', [{
    'include_paths': ('a.b.c', 'c.d'),
    'exclude_paths': ('c',)
}], indirect=True)
def test_in_app(elasticapm_client):
    include = elasticapm_client.include_paths_re
    exclude = elasticapm_client.exclude_paths_re
    frame1 = Mock(f_globals={'__name__': 'a.b.c'})
    frame2 = Mock(f_globals={'__name__': 'a.b.c.d'})
    frame3 = Mock(f_globals={'__name__': 'c.d'})

    info1 = stacks.get_frame_info(frame1, 1, False, include_paths_regex=include, exclude_paths_regex=exclude)
    info2 = stacks.get_frame_info(frame2, 1, False, include_paths_regex=include, exclude_paths_regex=exclude)
    info3 = stacks.get_frame_info(frame3, 1, False, include_paths_regex=include, exclude_paths_regex=exclude)
    assert info1['in_app']
    assert info2['in_app']
    assert not info3['in_app']


def test_get_frame_info():
    frame = get_me_a_test_frame()
    frame_info = stacks.get_frame_info(frame, frame.f_lineno, extended=True)

    assert frame_info['function'] == 'get_me_a_test_frame'
    assert frame_info['filename'] == 'tests/utils/stacks/__init__.py'
    assert frame_info['module'] == 'tests.utils.stacks'
    assert frame_info['lineno'] == 6
    assert frame_info['context_line'] == '    return inspect.currentframe()'
    assert frame_info['vars'] == {'a_local_var': 42}


def test_traceback_hide(elasticapm_client):
    def get_me_a_filtered_frame(hide=True):
        __traceback_hide__ = True
        if not hide:
            del __traceback_hide__

        return list(stacks.iter_stack_frames())

    # hide frame from `get_me_a_filtered_frame
    frames = list(stacks.get_stack_info(elasticapm_client, get_me_a_filtered_frame(True)))
    assert frames[0]['function'] == 'test_traceback_hide'

    # don't hide it:
    frames = list(stacks.get_stack_info(elasticapm_client, get_me_a_filtered_frame(False)))
    assert frames[0]['function'] == 'get_me_a_filtered_frame'
