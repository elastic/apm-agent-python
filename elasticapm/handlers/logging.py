"""
elasticapm.handlers.logging
~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2017 Elasticsearch

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

import datetime
import logging
import sys
import traceback

from elasticapm.base import Client
from elasticapm.utils import compat
from elasticapm.utils.encoding import to_unicode
from elasticapm.utils.stacks import iter_stack_frames


class LoggingHandler(logging.Handler):
    def __init__(self, *args, **kwargs):
        client = kwargs.pop("client_cls", Client)
        if len(args) == 1:
            arg = args[0]
            args = args[1:]
            if isinstance(arg, Client):
                self.client = arg
            else:
                raise ValueError(
                    "The first argument to %s must be a Client instance, "
                    "got %r instead." % (self.__class__.__name__, arg)
                )
        elif "client" in kwargs:
            self.client = kwargs.pop("client")
        else:
            self.client = client(*args, **kwargs)

        logging.Handler.__init__(self, level=kwargs.get("level", logging.NOTSET))

    def emit(self, record):
        self.format(record)

        # Avoid typical config issues by overriding loggers behavior
        if record.name.startswith("elasticapm.errors"):
            sys.stderr.write(to_unicode(record.message) + "\n")
            return

        try:
            return self._emit(record)
        except Exception:
            sys.stderr.write("Top level ElasticAPM exception caught - failed creating log record.\n")
            sys.stderr.write(to_unicode(record.msg + "\n"))
            sys.stderr.write(to_unicode(traceback.format_exc() + "\n"))

            try:
                self.client.capture("Exception")
            except Exception:
                pass

    def _emit(self, record, **kwargs):
        data = {}

        for k, v in compat.iteritems(record.__dict__):
            if "." not in k and k not in ("culprit",):
                continue
            data[k] = v

        stack = getattr(record, "stack", None)
        if stack is True:
            stack = iter_stack_frames()

        if stack:
            frames = []
            started = False
            last_mod = ""
            for item in stack:
                if isinstance(item, (list, tuple)):
                    frame, lineno = item
                else:
                    frame, lineno = item, item.f_lineno

                if not started:
                    f_globals = getattr(frame, "f_globals", {})
                    module_name = f_globals.get("__name__", "")
                    if last_mod.startswith("logging") and not module_name.startswith("logging"):
                        started = True
                    else:
                        last_mod = module_name
                        continue
                frames.append((frame, lineno))
            stack = frames

        custom = getattr(record, "data", {})
        # Add in all of the data from the record that we aren't already capturing
        for k in record.__dict__.keys():
            if k in (
                "stack",
                "name",
                "args",
                "msg",
                "levelno",
                "exc_text",
                "exc_info",
                "data",
                "created",
                "levelname",
                "msecs",
                "relativeCreated",
            ):
                continue
            if k.startswith("_"):
                continue
            custom[k] = record.__dict__[k]

        date = datetime.datetime.utcfromtimestamp(record.created)

        # If there's no exception being processed,
        # exc_info may be a 3-tuple of None
        # http://docs.python.org/library/sys.html#sys.exc_info
        if record.exc_info and all(record.exc_info):
            handler = self.client.get_handler("elasticapm.events.Exception")
            exception = handler.capture(self.client, exc_info=record.exc_info)
        else:
            exception = None

        return self.client.capture(
            "Message",
            param_message={"message": compat.text_type(record.msg), "params": record.args},
            stack=stack,
            custom=custom,
            exception=exception,
            date=date,
            level=record.levelno,
            logger_name=record.name,
            **kwargs
        )
