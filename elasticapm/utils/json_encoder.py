"""
elasticapm.utils.json_encoder
~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2017 Elasticsearch

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

import datetime
import uuid

try:
    import json
except ImportError:
    import simplejson as json


class BetterJSONEncoder(json.JSONEncoder):
    ENCODERS = {
        set: list,
        frozenset: list,
        datetime.datetime: lambda obj: obj.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        uuid.UUID: lambda obj: obj.hex,
        bytes: lambda obj: obj.decode("utf-8", errors="replace"),
    }

    def default(self, obj):
        if type(obj) in self.ENCODERS:
            return self.ENCODERS[type(obj)](obj)
        return super(BetterJSONEncoder, self).default(obj)


def better_decoder(data):
    return data


def dumps(value, **kwargs):
    return json.dumps(value, cls=BetterJSONEncoder, **kwargs)


def loads(value, **kwargs):
    return json.loads(value, object_hook=better_decoder)
