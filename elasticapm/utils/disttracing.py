import ctypes
import logging
from collections import namedtuple

logger = logging.getLogger("elasticapm.utils")

TraceParent = namedtuple("TraceParent", ["version", "trace_id", "span_id", "trace_options"])


class TracingOptions_bits(ctypes.LittleEndianStructure):
    _fields_ = [("traced", ctypes.c_uint8, 1)]  # asByte & 1


class TracingOptions(ctypes.Union):
    _anonymous_ = ("bit",)
    _fields_ = [("bit", TracingOptions_bits), ("asByte", ctypes.c_uint8)]


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
    return TraceParent(version, trace_id, span_id, trace_flags)
