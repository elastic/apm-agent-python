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

import decimal
import uuid

from elasticapm.utils import compat
from elasticapm.utils.encoding import enforce_label_format, shorten, transform


def test_transform_incorrect_unicode():
    x = "רונית מגן"

    result = transform(x)
    assert type(result) == str
    assert result == "רונית מגן"


def test_transform_correct_unicode():
    x = "רונית מגן"
    if compat.PY2:
        x = x.decode("utf-8")

    result = transform(x)
    assert type(result) == compat.text_type
    assert result == x


def test_transform_bad_string():
    x = compat.b("The following character causes problems: \xd4")

    result = transform(x)
    assert type(result) == compat.binary_type
    assert result == compat.b("(Error decoding value)")


def test_transform_float():
    result = transform(13.0)
    assert type(result) == float
    assert result == 13.0


def test_transform_bool():
    result = transform(True)
    assert type(result) == bool
    assert result == True


def test_transform_int_subclass():
    class X(int):
        pass

    result = transform(X())
    assert type(result) == int
    assert result == 0


# def test_transform_bad_string():
#     x = 'The following character causes problems: \xd4'

#     result = transform(x)
#     assert result == '(Error decoding value)'

# def test_transform_model_instance():
#     instance = DuplicateKeyModel(foo='foo')

#     result = transform(instance)
#     assert result == '<DuplicateKeyModel: foo>'

# def test_transform_handles_gettext_lazy():
#     from django.utils.functional import lazy
#     def fake_gettext(to_translate):
#         return u'Igpay Atinlay'

#     fake_gettext_lazy = lazy(fake_gettext, str)

#     self.assertEquals(
#         pickle.loads(pickle.dumps(
#                 transform(fake_gettext_lazy("something")))),
#         u'Igpay Atinlay')


def test_transform_dict_keys():
    x = {"foo": "bar"}

    result = transform(x)
    assert type(result) == dict
    keys = list(result.keys())
    assert len(keys) == 1
    assert type(keys[0]), str
    assert keys[0] == "foo"


def test_transform_dict_keys_utf8_as_str():
    x = {"רונית מגן": "bar"}

    result = transform(x)
    assert type(result) == dict
    keys = list(result.keys())
    assert len(keys) == 1
    assert type(keys[0]), compat.binary_type
    if compat.PY3:
        assert keys[0] == "רונית מגן"
    else:
        assert keys[0] == u"רונית מגן"


def test_transform_dict_keys_utf8_as_unicode():
    x = {compat.text_type("\u05e8\u05d5\u05e0\u05d9\u05ea \u05de\u05d2\u05df"): "bar"}

    result = transform(x)
    keys = list(result.keys())
    assert len(keys) == 1
    assert type(keys[0]), str
    assert keys[0] == "\u05e8\u05d5\u05e0\u05d9\u05ea \u05de\u05d2\u05df"


def test_transform_uuid():
    x = uuid.uuid4()
    result = transform(x)
    assert result == repr(x)
    assert type(result), str


def test_transform_recursive():
    x = []
    x.append(x)

    result = transform(x)
    assert result == ["<...>"]


def test_transform_custom_repr():
    class Foo(object):
        def __elasticapm__(self):
            return "example"

    x = Foo()

    result = transform(x)
    assert result == "example"


def test_transform_broken_repr():
    class Foo(object):
        def __repr__(self):
            raise ValueError

    x = Foo()

    result = transform(x)
    if compat.PY2:
        expected = u"<BadRepr: <class 'tests.utils.encoding.tests.Foo'>>"
    else:
        expected = "<BadRepr: <class 'tests.utils.encoding.tests.test_transform_broken_repr.<locals>.Foo'>>"
    assert result == expected


def test_shorten_string():
    result = shorten("hello world!", string_length=5)
    assert len(result) == 5
    assert result == "he..."


def test_shorten_lists():
    result = shorten(list(range(500)), list_length=50)
    assert len(result) == 52
    assert result[-2] == "..."
    assert result[-1] == "(450 more elements)"


def test_shorten_sets():
    result = shorten(set(range(500)), list_length=50)
    assert len(result) == 52
    assert result[-2] == "..."
    assert result[-1] == "(450 more elements)"


def test_shorten_frozenset():
    result = shorten(frozenset(range(500)), list_length=50)
    assert len(result) == 52
    assert result[-2] == "..."
    assert result[-1] == "(450 more elements)"


def test_shorten_tuple():
    result = shorten(tuple(range(500)), list_length=50)
    assert len(result) == 52
    assert result[-2] == "..."
    assert result[-1] == "(450 more elements)"

    # def test_shorten_generator():
    #     result = shorten(xrange(500))
    #     assert len(result) == 52
    #     assert result[-2] == '...'
    #     assert result[-1] == '(450 more elements)'


def test_enforce_label_format():
    class MyObj(object):
        def __str__(self):
            return "OK"

        def __unicode__(self):
            return u"OK"

    labels = enforce_label_format(
        {'a.b*c"d': MyObj(), "x": "x" * 1025, "int": 1, "float": 1.1, "decimal": decimal.Decimal("1")}
    )
    assert labels == {"a_b_c_d": "OK", "x": "x" * 1023 + u"…", "int": 1, "float": 1.1, "decimal": decimal.Decimal("1")}
