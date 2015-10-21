# -*- coding: utf-8 -*-
from __future__ import absolute_import

import uuid

from opbeat.utils import six
from opbeat.utils.encoding import shorten, transform
from tests.utils.compat import TestCase


class TransformTest(TestCase):
    def test_incorrect_unicode(self):
        x = 'רונית מגן'

        result = transform(x)
        self.assertEquals(type(result), str)
        self.assertEquals(result, 'רונית מגן')

    def test_correct_unicode(self):
        x = 'רונית מגן'
        if six.PY2:
            x = x.decode('utf-8')

        result = transform(x)
        self.assertEquals(type(result), six.text_type)
        self.assertEquals(result, x)

    def test_bad_string(self):
        x = six.b('The following character causes problems: \xd4')

        result = transform(x)
        self.assertEquals(type(result), six.binary_type)
        self.assertEquals(result, six.b('(Error decoding value)'))

    def test_float(self):
        result = transform(13.0)
        self.assertEquals(type(result), float)
        self.assertEquals(result, 13.0)

    def test_bool(self):
        result = transform(True)
        self.assertEquals(type(result), bool)
        self.assertEquals(result, True)

    def test_int_subclass(self):
        class X(int):
            pass

        result = transform(X())
        self.assertEquals(type(result), int)
        self.assertEquals(result, 0)

    # def test_bad_string(self):
    #     x = 'The following character causes problems: \xd4'

    #     result = transform(x)
    #     self.assertEquals(result, '(Error decoding value)')

    # def test_model_instance(self):
    #     instance = DuplicateKeyModel(foo='foo')

    #     result = transform(instance)
    #     self.assertEquals(result, '<DuplicateKeyModel: foo>')

    # def test_handles_gettext_lazy(self):
    #     from django.utils.functional import lazy
    #     def fake_gettext(to_translate):
    #         return u'Igpay Atinlay'

    #     fake_gettext_lazy = lazy(fake_gettext, str)

    #     self.assertEquals(
    #         pickle.loads(pickle.dumps(
    #                 transform(fake_gettext_lazy("something")))),
    #         u'Igpay Atinlay')

    def test_dict_keys(self):
        x = {'foo': 'bar'}

        result = transform(x)
        self.assertEquals(type(result), dict)
        keys = list(result.keys())
        self.assertEquals(len(keys), 1)
        self.assertTrue(type(keys[0]), str)
        self.assertEquals(keys[0], 'foo')

    def test_dict_keys_utf8_as_str(self):
        x = {'רונית מגן': 'bar'}

        result = transform(x)
        self.assertEquals(type(result), dict)
        keys = list(result.keys())
        self.assertEquals(len(keys), 1)
        self.assertTrue(type(keys[0]), six.binary_type)
        if six.PY3:
            self.assertEquals(keys[0], 'רונית מגן')
        else:
            self.assertEquals(keys[0], u'רונית מגן')

    def test_dict_keys_utf8_as_unicode(self):
        x = {
            six.text_type('\u05e8\u05d5\u05e0\u05d9\u05ea \u05de\u05d2\u05df'): 'bar'
        }

        result = transform(x)
        keys = list(result.keys())
        self.assertEquals(len(keys), 1)
        self.assertTrue(type(keys[0]), str)
        self.assertEquals(keys[0], '\u05e8\u05d5\u05e0\u05d9\u05ea \u05de\u05d2\u05df')

    def test_uuid(self):
        x = uuid.uuid4()
        result = transform(x)
        self.assertEquals(result, repr(x))
        self.assertTrue(type(result), str)

    def test_recursive(self):
        x = []
        x.append(x)

        result = transform(x)
        self.assertEquals(result, ['<...>'])

    def test_custom_repr(self):
        class Foo(object):
            def __opbeat__(self):
                return 'example'

        x = Foo()

        result = transform(x)
        self.assertEquals(result, 'example')

    def test_broken_repr(self):
        class Foo(object):
            def __repr__(self):
                raise ValueError

        x = Foo()

        result = transform(x)
        if six.PY2:
            expected = u"<BadRepr: <class 'tests.utils.encoding.tests.Foo'>>"
        else:
            expected = "<BadRepr: <class 'tests.utils.encoding.tests.TransformTest.test_broken_repr.<locals>.Foo'>>"
        self.assertEquals(result, expected)


class ShortenTest(TestCase):
    def test_shorten_string(self):
        result = shorten('hello world!', string_length=5)
        self.assertEquals(len(result), 5)
        self.assertEquals(result, 'he...')

    def test_shorten_lists(self):
        result = shorten(list(range(500)), list_length=50)
        self.assertEquals(len(result), 52)
        self.assertEquals(result[-2], '...')
        self.assertEquals(result[-1], '(450 more elements)')

    def test_shorten_sets(self):
        result = shorten(set(range(500)), list_length=50)
        self.assertEquals(len(result), 52)
        self.assertEquals(result[-2], '...')
        self.assertEquals(result[-1], '(450 more elements)')

    def test_shorten_frozenset(self):
        result = shorten(frozenset(range(500)), list_length=50)
        self.assertEquals(len(result), 52)
        self.assertEquals(result[-2], '...')
        self.assertEquals(result[-1], '(450 more elements)')

    def test_shorten_tuple(self):
        result = shorten(tuple(range(500)), list_length=50)
        self.assertEquals(len(result), 52)
        self.assertEquals(result[-2], '...')
        self.assertEquals(result[-1], '(450 more elements)')

    # def test_shorten_generator(self):
    #     result = shorten(xrange(500))
    #     self.assertEquals(len(result), 52)
    #     self.assertEquals(result[-2], '...')
    #     self.assertEquals(result[-1], '(450 more elements)')
