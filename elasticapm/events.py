"""
elasticapm.events
~~~~~~~~~~~~

:copyright: (c) 2011-2017 Elasticsearch

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

import logging
import random
import sys

from elasticapm.utils import varmap
from elasticapm.utils.encoding import keyword_field, shorten, to_unicode
from elasticapm.utils.stacks import get_culprit, get_stack_info, iter_traceback_frames

__all__ = ("BaseEvent", "Exception", "Message")

logger = logging.getLogger("elasticapm.events")


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
        exc = data["exception"]
        if exc["value"]:
            return "%s: %s" % (exc["type"], exc["value"])
        return exc["type"]

    @staticmethod
    def get_hash(data):
        exc = data["exception"]
        output = [exc["type"]]
        for frame in data["stacktrace"]["frames"]:
            output.append(frame["module"])
            output.append(frame["function"])
        return output

    @staticmethod
    def capture(client, exc_info=None, **kwargs):
        culprit = exc_value = exc_type = exc_module = frames = exc_traceback = None
        new_exc_info = False
        if not exc_info or exc_info is True:
            new_exc_info = True
            exc_info = sys.exc_info()

        if not exc_info:
            raise ValueError("No exception found")

        try:
            exc_type, exc_value, exc_traceback = exc_info

            frames = get_stack_info(
                iter_traceback_frames(exc_traceback),
                with_locals=client.config.collect_local_variables in ("errors", "all"),
                library_frame_context_lines=client.config.source_lines_error_library_frames,
                in_app_frame_context_lines=client.config.source_lines_error_app_frames,
                include_paths_re=client.include_paths_re,
                exclude_paths_re=client.exclude_paths_re,
                locals_processor_func=lambda local_var: varmap(
                    lambda k, val: shorten(
                        val,
                        list_length=client.config.local_var_list_max_length,
                        string_length=client.config.local_var_max_length,
                    ),
                    local_var,
                ),
            )

            culprit = get_culprit(frames, client.config.include_paths, client.config.exclude_paths)

            if hasattr(exc_type, "__module__"):
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
        if "message" in kwargs:
            message = kwargs["message"]
        else:
            message = "%s: %s" % (exc_type, to_unicode(exc_value)) if exc_value else str(exc_type)

        return {
            "id": "%032x" % random.getrandbits(128),
            "culprit": culprit,
            "exception": {
                "message": message,
                "type": keyword_field(str(exc_type)),
                "module": keyword_field(str(exc_module)),
                "stacktrace": frames,
            },
        }


class Message(BaseEvent):
    """
    Messages store the following metadata:

    - message: 'My message from %s about %s'
    - params: ('foo', 'bar')
    """

    @staticmethod
    def to_string(client, data):
        return data["log"]["message"]

    @staticmethod
    def get_hash(data):
        msg = data["param_message"]
        return [msg["message"]]

    @staticmethod
    def capture(client, param_message=None, message=None, level=None, logger_name=None, **kwargs):
        if message:
            param_message = {"message": message}
        params = param_message.get("params")
        message = param_message["message"] % params if params else param_message["message"]
        data = kwargs.get("data", {})
        message_data = {
            "id": "%032x" % random.getrandbits(128),
            "log": {
                "level": keyword_field(level or "error"),
                "logger_name": keyword_field(logger_name or "__root__"),
                "message": message,
                "param_message": keyword_field(param_message["message"]),
            },
        }
        if isinstance(data.get("stacktrace"), dict):
            message_data["log"]["stacktrace"] = data["stacktrace"]["frames"]
        if kwargs.get("exception"):
            message_data["culprit"] = kwargs["exception"]["culprit"]
            message_data["exception"] = kwargs["exception"]["exception"]
        return message_data
