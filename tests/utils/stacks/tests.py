# -*- coding: utf-8 -*-
from __future__ import absolute_import

from mock import Mock

from opbeat.utils import six
from opbeat.utils.stacks import get_culprit, get_stack_info
from tests.utils.compat import TestCase


class Context(object):
    def __init__(self, dict):
        self.dict = dict

    __getitem__ = lambda s, *a: s.dict.__getitem__(*a)
    __setitem__ = lambda s, *a: s.dict.__setitem__(*a)
    iterkeys = lambda s, *a: six.iterkeys(s.dict, *a)


class StackTest(TestCase):
    def test_get_culprit_bad_module(self):
        culprit = get_culprit([{
            'module': None,
            'function': 'foo',
        }])
        self.assertEquals(culprit, '<unknown>.foo')

        culprit = get_culprit([{
            'module': 'foo',
            'function': None,
        }])
        self.assertEquals(culprit, 'foo.<unknown>')

        culprit = get_culprit([{
        }])
        self.assertEquals(culprit, '<unknown>.<unknown>')

    def test_bad_locals_in_frame(self):
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
        self.assertEquals(len(results), 1)
        result = results[0]
        self.assertTrue('vars' in result)
        vars = {
            "foo": "bar",
            "biz": "baz",
        }
        self.assertEquals(result['vars'], vars)
