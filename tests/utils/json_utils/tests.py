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

import datetime
import decimal
import uuid

from elasticapm.utils import compat
from elasticapm.utils import json_encoder as json


def test_uuid():
    res = uuid.uuid4()
    assert json.dumps(res) == '"%s"' % res.hex


def test_datetime():
    res = datetime.datetime(day=1, month=1, year=2011, hour=1, minute=1, second=1)
    assert json.dumps(res) == '"2011-01-01T01:01:01.000000Z"'


def test_set():
    res = set(["foo", "bar"])
    assert json.dumps(res) in ('["foo", "bar"]', '["bar", "foo"]')


def test_frozenset():
    res = frozenset(["foo", "bar"])
    assert json.dumps(res) in ('["foo", "bar"]', '["bar", "foo"]')


def test_bytes():
    if compat.PY2:
        res = bytes("foobar")
    else:
        res = bytes("foobar", encoding="ascii")
    assert json.dumps(res) == '"foobar"'


def test_decimal():
    res = decimal.Decimal("1.0")
    assert json.dumps(res) == "1.0"
