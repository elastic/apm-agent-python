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

import binascii
import ctypes
import itertools
import random
import re
from typing import Dict, Optional

from elasticapm.conf import constants
from elasticapm.utils.logging import get_logger

logger = get_logger("elasticapm.utils")


class TraceParent(object):
    __slots__ = ("version", "trace_id", "span_id", "trace_options", "tracestate", "tracestate_dict", "is_legacy")

    def __init__(
        self,
        version: int,
        trace_id: str,
        span_id: str,
        trace_options: "TracingOptions",
        tracestate: Optional[str] = None,
        is_legacy: bool = False,
    ):
        self.version: int = version
        self.trace_id: str = trace_id
        self.span_id: str = span_id
        self.trace_options: TracingOptions = trace_options
        self.is_legacy: bool = is_legacy
        self.tracestate: Optional[str] = tracestate
        self.tracestate_dict = self._parse_tracestate(tracestate)

    def copy_from(
        self,
        version: int = None,
        trace_id: str = None,
        span_id: str = None,
        trace_options: "TracingOptions" = None,
        tracestate: str = None,
    ):
        return TraceParent(
            version or self.version,
            trace_id or self.trace_id,
            span_id or self.span_id,
            trace_options or self.trace_options,
            tracestate or self.tracestate,
        )

    def to_string(self) -> str:
        return "{:02x}-{}-{}-{:02x}".format(self.version, self.trace_id, self.span_id, self.trace_options.asByte)

    def to_ascii(self) -> bytes:
        return self.to_string().encode("ascii")

    def to_binary(self) -> bytes:
        return b"".join(
            [
                (self.version).to_bytes(1, byteorder="big"),
                (0).to_bytes(1, byteorder="big"),
                bytes.fromhex(self.trace_id),
                (1).to_bytes(1, byteorder="big"),
                bytes.fromhex(self.span_id),
                (2).to_bytes(1, byteorder="big"),
                (self.trace_options.asByte).to_bytes(1, byteorder="big"),
            ]
        )

    @classmethod
    def new(cls, transaction_id: str, is_sampled: bool) -> "TraceParent":
        return cls(
            version=constants.TRACE_CONTEXT_VERSION,
            trace_id="%032x" % random.getrandbits(128),
            span_id=transaction_id,
            trace_options=TracingOptions(recorded=is_sampled),
        )

    @classmethod
    def from_string(
        cls, traceparent_string: str, tracestate_string: Optional[str] = None, is_legacy: bool = False
    ) -> Optional["TraceParent"]:
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
        headers: dict,
        header_name: str = constants.TRACEPARENT_HEADER_NAME,
        legacy_header_name: str = constants.TRACEPARENT_LEGACY_HEADER_NAME,
        tracestate_header_name: str = constants.TRACESTATE_HEADER_NAME,
    ) -> Optional["TraceParent"]:
        tracestate = cls.merge_duplicate_headers(headers, tracestate_header_name)
        if header_name in headers:
            return TraceParent.from_string(headers[header_name], tracestate, is_legacy=False)
        elif legacy_header_name in headers:
            return TraceParent.from_string(headers[legacy_header_name], tracestate, is_legacy=False)
        else:
            return None

    @classmethod
    def from_binary(cls, data: bytes) -> Optional["TraceParent"]:
        if len(data) != 29:
            logger.debug("Invalid binary traceparent format, length is %d, should be 29, value %r", len(data), data)
            return
        if (
            int.from_bytes(data[1:2], byteorder="big") != 0
            or int.from_bytes(data[18:19], byteorder="big") != 1
            or int.from_bytes(data[27:28], byteorder="big") != 2
        ):
            logger.debug("Invalid binary traceparent format, field identifiers not correct, value %r", data)
            return
        version = int.from_bytes(data[0:1], byteorder="big")
        trace_id = str(binascii.hexlify(data[2:18]), encoding="ascii")
        span_id = str(binascii.hexlify(data[19:27]), encoding="ascii")
        try:
            tracing_options = TracingOptions()
            tracing_options.asByte = int.from_bytes(data[28:29], byteorder="big")
        except ValueError:
            logger.debug("Invalid trace-options field, value %r", data[28:29])
            return
        return TraceParent(version, trace_id, span_id, tracing_options)

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
        if isinstance(headers, list):
            return ",".join([item[1] for item in headers if item[0] == key])
        elif not hasattr(headers, "get") and hasattr(headers, "__iter__"):
            return ",".join([item[1] for item in headers if item[0] == key])
        return headers.get(key)

    def _parse_tracestate(self, tracestate) -> Dict[str, str]:
        """
        Tracestate can contain data from any vendor, made distinct by vendor
        keys. Vendors are comma-separated. The elastic (es) tracestate data is
        made up of key:value pairs, separated by semicolons. It is meant to
        be parsed into a dict.

            tracestate: es=key:value;key:value... , othervendor=<opaque>

        Per https://w3c.github.io/trace-context/#tracestate-header-field-values
        there can be optional whitespace (OWS) between the comma-separated
        list-members.
        """
        if not tracestate:
            return {}
        if "es=" not in tracestate:
            return {}

        ret = {}
        try:
            state = re.search(r"(?:,|^)\s*es=([^,]*?)\s*(?:,|$)", tracestate).group(1).split(";")
        except IndexError:
            return {}
        for keyval in state:
            if not keyval:
                continue
            key, _, val = keyval.partition(":")
            ret[key] = val

        return ret

    def _set_tracestate(self):
        elastic_value = ";".join(["{}:{}".format(k, v) for k, v in self.tracestate_dict.items()])
        # No character validation needed, as we validate in `add_tracestate`. Just validate length.
        if len(elastic_value) > 256:
            logger.debug("Modifications to TraceState would violate length limits, ignoring.")
            raise TraceStateFormatException()
        elastic_state = "es={}".format(elastic_value)
        if not self.tracestate:
            return elastic_state
        else:
            # Remove es=<stuff> from the tracestate, and add the new es state to the end
            otherstate = re.sub(r"(?:,|^)\s*es=([^,]*?)\s*(?:,|$)", "", self.tracestate)
            otherstate = otherstate.lstrip(",")  # in case `es=` was the first entry
            otherstate = re.sub(r",,", ",", otherstate)  # remove potential double commas
            # No validation of `otherstate` required, since we're downstream. We only need to check `es=`
            # since we introduced it, and that validation has already been done at this point.
            if otherstate:
                return "{},{}".format(otherstate.rstrip(","), elastic_state)
            else:
                return elastic_state

    def add_tracestate(self, key, val):
        """
        Add key/value pair to the tracestate.

        We do most of the validation for valid characters here. We have to make
        sure none of the reserved separators for tracestate are used in our
        key/value pairs, and we also need to check that all characters are
        within the valid range. Checking here means we never have to re-check
        a pair once set, which saves time in the _set_tracestate() function.
        """
        key = str(key)
        val = str(val)
        for bad in (":", ";", ",", "="):
            if bad in key or bad in val:
                logger.debug("New tracestate key/val pair contains invalid character '{}', ignoring.".format(bad))
                return
        for c in itertools.chain(key, val):
            # Tracestate spec only allows for characters between ASCII 0x20 and 0x7E
            if ord(c) < 0x20 or ord(c) > 0x7E:
                logger.debug("Modifications to TraceState would introduce invalid character '{}', ignoring.".format(c))
                return

        oldval = self.tracestate_dict.pop(key, None)
        self.tracestate_dict[key] = val
        try:
            self.tracestate = self._set_tracestate()
        except TraceStateFormatException:
            if oldval is not None:
                self.tracestate_dict[key] = oldval
            else:
                self.tracestate_dict.pop(key)


class TracingOptions_bits(ctypes.LittleEndianStructure):
    _fields_ = [("recorded", ctypes.c_uint8, 1)]


class TracingOptions(ctypes.Union):
    _anonymous_ = ("bit",)
    _fields_ = [("bit", TracingOptions_bits), ("asByte", ctypes.c_uint8)]

    def __init__(self, **kwargs):
        super(TracingOptions, self).__init__()
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __eq__(self, other):
        return self.asByte == other.asByte


def trace_parent_from_string(traceparent_string, tracestate_string=None, is_legacy=False):
    """
    This is a wrapper function so we can add traceparent generation to the
    public API.
    """
    return TraceParent.from_string(traceparent_string, tracestate_string=tracestate_string, is_legacy=is_legacy)


def trace_parent_from_headers(headers):
    """
    This is a wrapper function so we can add traceparent generation to the
    public API.
    """
    return TraceParent.from_headers(headers)


class TraceStateFormatException(Exception):
    pass
