"""
opbeat.events
~~~~~~~~~~~~

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

import logging
import sys

from opbeat.utils import varmap
from opbeat.utils.encoding import shorten, to_unicode
from opbeat.utils.stacks import (get_culprit, get_stack_info,
                                 iter_traceback_frames)

__all__ = ('BaseEvent', 'Exception', 'Message', 'Query')


class BaseEvent(object):
    def __init__(self, client):
        self.client = client
        self.logger = logging.getLogger(__name__)

    def to_string(self, data):
        raise NotImplementedError

    def capture(self, **kwargs):
        return {}


class Exception(BaseEvent):
    """
    Exceptions store the following metadata:

    - value: 'My exception value'
    - type: 'ClassName'
    - module '__builtin__' (i.e. __builtin__.TypeError)
    - frames: a list of serialized frames (see _get_traceback_frames)
    """

    def to_string(self, data):
        exc = data['exception']
        if exc['value']:
            return '%s: %s' % (exc['type'], exc['value'])
        return exc['type']

    def get_hash(self, data):
        exc = data['exception']
        output = [exc['type']]
        for frame in data['stacktrace']['frames']:
            output.append(frame['module'])
            output.append(frame['function'])
        return output

    def capture(self, exc_info=None, **kwargs):
        new_exc_info = False
        if not exc_info or exc_info is True:
            new_exc_info = True
            exc_info = sys.exc_info()

        if not exc_info:
            raise ValueError('No exception found')

        try:
            exc_type, exc_value, exc_traceback = exc_info

            frames = varmap(
                lambda k, v: shorten(v,
                                     string_length=self.client.string_max_length,
                                     list_length=self.client.list_max_length
                                     ),
                get_stack_info((iter_traceback_frames(exc_traceback)))
            )

            culprit = get_culprit(frames, self.client.include_paths,
                                  self.client.exclude_paths)

            if hasattr(exc_type, '__module__'):
                exc_module = exc_type.__module__
                exc_type = exc_type.__name__
            else:
                exc_module = None
                exc_type = exc_type.__name__
        finally:
            if new_exc_info:
                try:
                    del exc_info
                    del exc_traceback
                except Exception as e:
                    self.logger.exception(e)

        return {
            'level': logging.ERROR,
            'culprit': culprit,
            'exception': {
                'value': to_unicode(exc_value),
                'type': str(exc_type),
                'module': str(exc_module),
            },
            'stacktrace': {
                'frames': frames
            },
        }


class Message(BaseEvent):
    """
    Messages store the following metadata:

    - message: 'My message from %s about %s'
    - params: ('foo', 'bar')
    """

    def to_string(self, data):
        msg = data['param_message']
        if msg.get('params'):
            return msg['message'] % msg['params']
        return msg['message']

    def get_hash(self, data):
        msg = data['param_message']
        return [msg['message']]

    def capture(self, param_message=None, message=None, **kwargs):
        if message:
            param_message = {'message': message}

        params = param_message.get('params', ())
        data = {
            'param_message': {
                'message': param_message['message'],
                'params': params,
            }
        }
        return data


class Query(BaseEvent):
    """
    Messages store the following metadata:

    - query: 'SELECT * FROM table'
    - engine: 'postgesql_psycopg2'
    """

    def to_string(self, data):
        sql = data['query']
        return sql['query']

    def get_hash(self, data):
        sql = data['query']
        return [sql['query'], sql['engine']]

    def capture(self, query, engine, **kwargs):
        return {
            'query': {
                'query': query,
                'engine': engine,
            }
        }
