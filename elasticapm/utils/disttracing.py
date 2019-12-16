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

import ctypes

from elasticapm.conf import constants
from elasticapm.utils.logging import get_logger

logger = get_logger("elasticapm.utils")


class TraceParent(object):
    __slots__ = ("version", "trace_id", "span_id", "trace_options", "tracestate", "is_legacy")

    def __init__(self, version, trace_id, span_id, trace_options, tracestate=None, is_legacy=False):
        self.version = version
        self.trace_id = trace_id
        self.span_id = span_id
        self.trace_options = trace_options
        self.is_legacy = is_legacy
        self.tracestate = tracestate

    def copy_from(self, version=None, trace_id=None, span_id=None, trace_options=None, tracestate=None):
        return TraceParent(
            version or self.version,
            trace_id or self.trace_id,
            span_id or self.span_id,
            trace_options or self.trace_options,
            tracestate or self.tracestate,
        )

    def to_string(self):
        return "{:02x}-{}-{}-{:02x}".format(self.version, self.trace_id, self.span_id, self.trace_options.asByte)

    def to_ascii(self):
        return self.to_string().encode("ascii")

    @classmethod
    def from_string(cls, traceparent_string, tracestate_string=None, is_legacy=False):
        try:
            parts = traceparent_string.split("-")
            version, trace_id, span_id, trace_flags = parts[:4]
        except ValueError:
            logger.debug("Invalid traceparent header format, value %s", traceparent_string)
            return
        try:
            version = int(version, 16)
            if version == 255:
                raise ValueError()
        except ValueError:
            logger.debug("Invalid version field, value %s", version)
            return
        try:
            tracing_options = TracingOptions()
            tracing_options.asByte = int(trace_flags, 16)
        except ValueError:
            logger.debug("Invalid trace-options field, value %s", trace_flags)
            return
        return TraceParent(version, trace_id, span_id, tracing_options, tracestate_string, is_legacy)

    @classmethod
    def from_headers(
        cls,
        headers,
        header_name=constants.TRACEPARENT_HEADER_NAME,
        legacy_header_name=constants.TRACEPARENT_LEGACY_HEADER_NAME,
        tracestate_header_name=constants.TRACESTATE_HEADER_NAME,
    ):
        tracestate = cls.merge_duplicate_headers(headers, tracestate_header_name)
        if header_name in headers:
            return TraceParent.from_string(headers[header_name], tracestate, is_legacy=False)
        elif legacy_header_name in headers:
            return TraceParent.from_string(headers[legacy_header_name], tracestate, is_legacy=False)
        else:
            return None

    @classmethod
    def merge_duplicate_headers(cls, headers, key):
        """
        HTTP allows multiple values for the same header name. Most WSGI implementations
        merge these values using a comma as separator (this has been confirmed for wsgiref,
        werkzeug, gunicorn and uwsgi). Other implementations may use containers like
        multidict to store headers and have APIs to iterate over all values for a given key.

        This method is provided as a hook for framework integrations to provide their own
        TraceParent implementation. The implementation should return a single string. Multiple
        values for the same key should be merged using a comma as separator.

        :param headers: a dict-like header object
        :param key: header name
        :return: a single string value or None
        """
        # this works for all known WSGI implementations
        return headers.get(key)


class TracingOptions_bits(ctypes.LittleEndianStructure):
    _fields_ = [("recorded", ctypes.c_uint8, 1)]


class TracingOptions(ctypes.Union):
    _anonymous_ = ("bit",)
    _fields_ = [("bit", TracingOptions_bits), ("asByte", ctypes.c_uint8)]

    def __init__(self, **kwargs):
        super(TracingOptions, self).__init__()
        for k, v in kwargs.items():
            setattr(self, k, v)
