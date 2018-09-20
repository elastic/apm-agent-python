import ctypes
import logging
from collections import namedtuple

from elasticapm.utils import compat

logger = logging.getLogger("elasticapm.utils")

TraceParent = namedtuple("TraceParent", ["version", "trace_id", "span_id", "trace_options"])


class TraceParent(object):
    __slots__ = ("version", "trace_id", "span_id", "trace_options")

    def __init__(self, version, trace_id, span_id, trace_options):
        self.version = version
        self.trace_id = trace_id
        self.span_id = span_id
        self.trace_options = trace_options

    def copy_from(self, version=None, trace_id=None, span_id=None, trace_options=None):
        return TraceParent(
            version or self.version,
            trace_id or self.trace_id,
            span_id or self.span_id,
            trace_options or self.trace_options,
        )

    def to_ascii(self):
        return u"{:02x}-{}-{}-{:02x}".format(
            self.version, self.trace_id, self.span_id, self.trace_options.asByte
        ).encode("ascii")


class TracingOptions_bits(ctypes.LittleEndianStructure):
    _fields_ = [("requested", ctypes.c_uint8, 1), ("recorded", ctypes.c_uint8, 1)]


class TracingOptions(ctypes.Union):
    _anonymous_ = ("bit",)
    _fields_ = [("bit", TracingOptions_bits), ("asByte", ctypes.c_uint8)]

    def __init__(self, **kwargs):
        super(TracingOptions, self).__init__()
        for k, v in kwargs.items():
            setattr(self, k, v)


def parse_traceparent_header(header_value):
    try:
        version, trace_id, span_id, trace_flags = header_value.split("-")
    except ValueError:
        logger.debug("Wrong traceparent header format, value %s", header_value)
        return
    try:
        version = int(version, 16)
    except ValueError:
        logger.debug("Can't parse version field, value %s", version)
        return
    try:
        tracing_options = TracingOptions()
        tracing_options.asByte = int(trace_flags, 16)
    except ValueError:
        logger.debug("Can't parse trace-options field, value %s", trace_flags)
        return
    return TraceParent(version, trace_id, span_id, tracing_options)
