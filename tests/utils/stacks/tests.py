# -*- coding: utf-8 -*-
from __future__ import absolute_import

from mock import Mock

from elasticapm.utils import compat
from elasticapm.utils.stacks import get_culprit, get_stack_info


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
    vars = {
        "foo": "bar",
        "biz": "baz",
    }
    assert result['vars'] == vars
