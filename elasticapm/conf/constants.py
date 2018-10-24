EVENTS_API_PATH = "/intake/v2/events"

TRACE_CONTEXT_VERSION = 0
TRACEPARENT_HEADER_NAME = "elastic-apm-traceparent"

TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

KEYWORD_MAX_LENGTH = 1024

HTTP_WITH_BODY = {"POST", "PUT", "PATCH", "DELETE"}

ERROR = "error"
TRANSACTION = "transaction"
SPAN = "span"
