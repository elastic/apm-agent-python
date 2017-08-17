"""
elasticapm.events
~~~~~~~~~~~~

:copyright: (c) 2011-2017 Elasticsearch

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

import logging
import sys
import uuid

from elasticapm.utils import varmap
from elasticapm.utils.encoding import shorten, to_unicode
from elasticapm.utils.stacks import (get_culprit, get_stack_info,
                                     iter_traceback_frames)

__all__ = ('BaseEvent', 'Exception', 'Message', 'Query')

logger = logging.getLogger(__name__)


class BaseEvent(object):
    @staticmethod
    def to_string(client, data):
        raise NotImplementedError

    @staticmethod
    def capture(client, **kwargs):
        return {}


class Exception(BaseEvent):
    """
    Exceptions store the following metadata:

    - value: 'My exception value'
    - type: 'ClassName'
    - module '__builtin__' (i.e. __builtin__.TypeError)
    - frames: a list of serialized frames (see _get_traceback_frames)
    """

    @staticmethod
    def to_string(client, data):
        exc = data['exception']
        if exc['value']:
            return '%s: %s' % (exc['type'], exc['value'])
        return exc['type']

    @staticmethod
    def get_hash(data):
        exc = data['exception']
        output = [exc['type']]
        for frame in data['stacktrace']['frames']:
            output.append(frame['module'])
            output.append(frame['function'])
        return output

    @staticmethod
    def capture(client, exc_info=None, **kwargs):
        culprit = exc_value = exc_type = exc_module = frames = None
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
                                     string_length=client.string_max_length,
                                     list_length=client.list_max_length
                                     ),
                get_stack_info((iter_traceback_frames(exc_traceback)))
            )

            culprit = get_culprit(frames, client.include_paths,
                                  client.exclude_paths)

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
                    logger.exception(e)

        return {
            'id': str(uuid.uuid4()),
            'culprit': culprit,
            'exception': {
                'message': '%s: %s' % (exc_type, to_unicode(exc_value)) if exc_value else str(exc_type),
                'type': str(exc_type),
                'module': str(exc_module),
                'stacktrace':  frames,
            }
        }


class Message(BaseEvent):
    """
    Messages store the following metadata:

    - message: 'My message from %s about %s'
    - params: ('foo', 'bar')
    """

    @staticmethod
    def to_string(client, data):
        return data['log']['message']

    @staticmethod
    def get_hash(data):
        msg = data['param_message']
        return [msg['message']]

    @staticmethod
    def capture(client, param_message=None, message=None, **kwargs):
        if message:
            param_message = {'message': message}
        params = param_message.get('params', ())
        message = param_message['message'] % params
        data = kwargs.get('data', {})
        message_data = {
            'id': str(uuid.uuid4()),
            'log': {
                'level': data.get('level', 'error'),
                'logger_name': data.get('logger'),
                'message': message,
                'param_message': param_message['message'],
            }
        }
        if isinstance(data.get('stacktrace'), dict):
            message_data['log']['stacktrace'] = data['stacktrace']['frames']
        return message_data


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
