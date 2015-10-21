"""
opbeat.core.processors
~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

import re

from opbeat.utils import six, varmap
from opbeat.utils.encoding import force_text


class Processor(object):
    def __init__(self, client):
        self.client = client

    def get_data(self, data, **kwargs):
        return

    def process(self, data, **kwargs):
        resp = self.get_data(data, **kwargs)
        if resp:
            data = resp
        return data


class RemovePostDataProcessor(Processor):
    """
    Removes HTTP post data.
    """
    def process(self, data, **kwargs):
        if 'http' in data:
            data['http'].pop('data', None)

        return data


class RemoveStackLocalsProcessor(Processor):
    """
    Removes local context variables from stacktraces.
    """
    def process(self, data, **kwargs):
        if 'stacktrace' in data:
            for frame in data['stacktrace'].get('frames', []):
                frame.pop('vars', None)

        return data


class SanitizePasswordsProcessor(Processor):
    """
    Asterisk out passwords from password fields in frames, http,
    and basic extra data.
    """
    MASK = '*' * 8
    FIELDS = frozenset([
        'password',
        'secret',
        'passwd',
        'token',
        'api_key',
        'access_token',
        'sessionid',
    ])
    VALUES_RE = re.compile(r'^\d{16}$')

    def sanitize(self, key, value):
        if value is None:
            return

        if isinstance(value, six.string_types) and self.VALUES_RE.match(value):
            return self.MASK

        if not key:  # key can be a NoneType
            return value

        key = key.lower()
        for field in self.FIELDS:
            if field in key:
                # store mask as a fixed length for security
                return self.MASK
        return value

    def filter_stacktrace(self, data):
        if 'frames' not in data:
            return
        for frame in data['frames']:
            if 'vars' not in frame:
                continue
            frame['vars'] = varmap(self.sanitize, frame['vars'])

    def filter_http(self, data):
        for n in ('data', 'cookies', 'headers', 'env', 'query_string'):
            if n not in data:
                continue

            if isinstance(data[n], (six.binary_type,) + six.string_types):
                text_data = force_text(data[n], errors='replace')
                if '=' in text_data:
                    # at this point we've assumed it's a standard HTTP query
                    querybits = []
                    for bit in text_data.split('&'):
                        chunk = bit.split('=')
                        if len(chunk) == 2:
                            querybits.append((chunk[0], self.sanitize(*chunk)))
                        else:
                            querybits.append(chunk)

                    data[n] = '&'.join('='.join(k) for k in querybits)
                    continue
            data[n] = varmap(self.sanitize, data[n])

    def process(self, data, **kwargs):
        if 'stacktrace' in data:
            self.filter_stacktrace(data['stacktrace'])

        if 'http' in data:
            self.filter_http(data['http'])

        return data
