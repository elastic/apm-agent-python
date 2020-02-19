#  BSD 3-Clause License
#
#  Copyright (c) 2012, the Sentry Team, see AUTHORS for more details
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


import random
import sys

from elasticapm.conf.constants import EXCEPTION_CHAIN_MAX_DEPTH
from elasticapm.utils import compat, varmap
from elasticapm.utils.encoding import keyword_field, shorten, to_unicode
from elasticapm.utils.logging import get_logger
from elasticapm.utils.stacks import get_culprit, get_stack_info, iter_traceback_frames

__all__ = ("BaseEvent", "Exception", "Message")

logger = get_logger("elasticapm.events")


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

        if exc_info == (None, None, None):
            raise ValueError("No exception found: capture_exception requires an active exception.")

        try:
            exc_type, exc_value, exc_traceback = exc_info

            frames = get_stack_info(
                iter_traceback_frames(exc_traceback, config=client.config),
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
                        dict_length=client.config.local_var_dict_max_length,
                    ),
                    local_var,
                ),
            )

            culprit = kwargs.get("culprit", None) or get_culprit(
                frames, client.config.include_paths, client.config.exclude_paths
            )

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

        data = {
            "id": "%032x" % random.getrandbits(128),
            "culprit": keyword_field(culprit),
            "exception": {
                "message": message,
                "type": keyword_field(str(exc_type)),
                "module": keyword_field(str(exc_module)),
                "stacktrace": frames,
            },
        }
        if hasattr(exc_value, "_elastic_apm_span_id"):
            data["parent_id"] = exc_value._elastic_apm_span_id
            del exc_value._elastic_apm_span_id
        if compat.PY3:
            depth = kwargs.get("_exc_chain_depth", 0)
            if depth > EXCEPTION_CHAIN_MAX_DEPTH:
                return
            cause = exc_value.__cause__
            chained_context = exc_value.__context__

            # we follow the pattern of Python itself here and only capture the chained exception
            # if cause is not None and __suppress_context__ is False
            if chained_context and not (exc_value.__suppress_context__ and cause is None):
                if cause:
                    chained_exc_type = type(cause)
                    chained_exc_value = cause
                else:
                    chained_exc_type = type(chained_context)
                    chained_exc_value = chained_context
                chained_exc_info = chained_exc_type, chained_exc_value, chained_context.__traceback__

                chained_cause = Exception.capture(
                    client, exc_info=chained_exc_info, culprit="None", _exc_chain_depth=depth + 1
                )
                if chained_cause:
                    data["exception"]["cause"] = [chained_cause["exception"]]
        return data


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
