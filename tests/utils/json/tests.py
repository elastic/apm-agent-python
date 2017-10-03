# -*- coding: utf-8 -*-
from __future__ import absolute_import

import datetime
import uuid

from elasticapm.utils import json_encoder as json
from elasticapm.utils import compat


def test_uuid():
    res = uuid.uuid4()
    assert json.dumps(res) == '"%s"' % res.hex


def test_datetime():
    res = datetime.datetime(day=1, month=1, year=2011, hour=1, minute=1, second=1)
    assert json.dumps(res) == '"2011-01-01T01:01:01.000000Z"'


def test_set():
    res = set(['foo', 'bar'])
    assert json.dumps(res) in ('["foo", "bar"]', '["bar", "foo"]')


def test_frozenset():
    res = frozenset(['foo', 'bar'])
    assert json.dumps(res) in ('["foo", "bar"]', '["bar", "foo"]')


def test_bytes():
    if compat.PY2:
        res = bytes('foobar')
    else:
        res = bytes('foobar', encoding='ascii')
    assert json.dumps(res) == '"foobar"'
