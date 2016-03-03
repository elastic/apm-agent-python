"""
opbeat.handlers.logging
~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

import datetime
import logging
import sys
import traceback

from opbeat.base import Client
from opbeat.utils import six
from opbeat.utils.encoding import to_string
from opbeat.utils.stacks import iter_stack_frames


class OpbeatHandler(logging.Handler, object):
    def __init__(self, *args, **kwargs):
        client = kwargs.pop('client_cls', Client)
        if len(args) == 1:
            arg = args[0]
            args = args[1:]
            if isinstance(arg, Client):
                self.client = arg
            else:
                raise ValueError(
                    'The first argument to %s must be a Client instance, '
                    'got %r instead.' % (
                        self.__class__.__name__,
                        arg,
                    ))
        elif 'client' in kwargs:
            self.client = kwargs.pop('client')
        else:
            self.client = client(*args, **kwargs)

        super(OpbeatHandler, self).__init__(*args, **kwargs)

    def emit(self, record):
        self.format(record)

        # Avoid typical config issues by overriding loggers behavior
        if record.name.startswith('opbeat.errors'):
            six.print_(to_string(record.message), file=sys.stderr)
            return

        try:
            return self._emit(record)
        except Exception:
            six.print_(
                "Top level Opbeat exception caught - "
                "failed creating log record",
                sys.stderr)
            six.print_(to_string(record.msg), sys.stderr)
            six.print_(to_string(traceback.format_exc()), sys.stderr)

            try:
                self.client.capture('Exception')
            except Exception:
                pass

    def _emit(self, record, **kwargs):
        data = {}

        for k, v in six.iteritems(record.__dict__):
            if '.' not in k and k not in ('culprit',):
                continue
            data[k] = v

        stack = getattr(record, 'stack', None)
        if stack is True:
            stack = iter_stack_frames()

        if stack:
            frames = []
            started = False
            last_mod = ''
            for item in stack:
                if isinstance(item, (list, tuple)):
                    frame, lineno = item
                else:
                    frame, lineno = item, item.f_lineno

                if not started:
                    f_globals = getattr(frame, 'f_globals', {})
                    module_name = f_globals.get('__name__', '')
                    if last_mod.startswith(
                            'logging') and not module_name.startswith(
                            'logging'):
                        started = True
                    else:
                        last_mod = module_name
                        continue
                frames.append((frame, lineno))
            stack = frames

        extra = getattr(record, 'data', {})
        # Add in all of the data from the record that we aren't already capturing
        for k in record.__dict__.keys():
            if k in (
                    'stack', 'name', 'args', 'msg', 'levelno', 'exc_text',
                    'exc_info', 'data', 'created', 'levelname', 'msecs',
                    'relativeCreated'):
                continue
            if k.startswith('_'):
                continue
            extra[k] = record.__dict__[k]

        date = datetime.datetime.utcfromtimestamp(record.created)

        # If there's no exception being processed,
        # exc_info may be a 3-tuple of None
        # http://docs.python.org/library/sys.html#sys.exc_info
        if record.exc_info and all(record.exc_info):
            handler = self.client.get_handler('opbeat.events.Exception')

            data.update(handler.capture(exc_info=record.exc_info))
            # data['checksum'] = handler.get_hash(data)

        data['level'] = record.levelno
        data['logger'] = record.name

        return self.client.capture('Message',
                                   param_message={'message': record.msg,
                                                  'params': record.args},
                                   stack=stack, data=data, extra=extra,
                                   date=date, **kwargs)
