"""
elasticapm.core.processors
~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2017 Elasticsearch

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

import re
import warnings

from elasticapm.conf.constants import ERROR, SPAN, TRANSACTION
from elasticapm.utils import compat, varmap
from elasticapm.utils.encoding import force_text

MASK = 8 * "*"

SANITIZE_FIELD_NAMES = frozenset(
    ["authorization", "password", "secret", "passwd", "token", "api_key", "access_token", "sessionid"]
)

SANITIZE_VALUE_PATTERNS = [re.compile(r"^[- \d]{16,19}$")]  # credit card numbers, with or without spacers


def for_events(*events):
    """
    :param events: list of event types

    Only calls wrapped function if given event_type is in list of events
    """
    events = set(events)

    def wrap(func):
        func.event_types = events
        return func

    return wrap


@for_events(ERROR, TRANSACTION)
def remove_http_request_body(client, event):
    """
    Removes request.body from context

    :param client: an ElasticAPM client
    :param event: a transaction or error event
    :return: The modified event
    """
    if "context" in event and "request" in event["context"]:
        event["context"]["request"].pop("body", None)
    return event


@for_events(ERROR, SPAN)
def remove_stacktrace_locals(client, event):
    """
    Removes local variables from any frames.

    :param client: an ElasticAPM client
    :param event: a transaction or error event
    :return: The modified event
    """
    func = lambda frame: frame.pop("vars", None)
    return _process_stack_frames(event, func)


@for_events(ERROR, SPAN)
def sanitize_stacktrace_locals(client, event):
    """
    Sanitizes local variables in all frames

    :param client: an ElasticAPM client
    :param event: a transaction or error event
    :return: The modified event
    """

    def func(frame):
        if "vars" in frame:
            frame["vars"] = varmap(_sanitize, frame["vars"])

    return _process_stack_frames(event, func)


@for_events(ERROR, TRANSACTION)
def sanitize_http_request_cookies(client, event):
    """
    Sanitizes http request cookies

    :param client: an ElasticAPM client
    :param event: a transaction or error event
    :return: The modified event
    """

    # sanitize request.cookies dict
    try:
        cookies = event["context"]["request"]["cookies"]
        event["context"]["request"]["cookies"] = varmap(_sanitize, cookies)
    except (KeyError, TypeError):
        pass

    # sanitize request.header.cookie string
    try:
        cookie_string = event["context"]["request"]["headers"]["cookie"]
        event["context"]["request"]["headers"]["cookie"] = _sanitize_string(cookie_string, "; ", "=")
    except (KeyError, TypeError):
        pass
    return event


@for_events(ERROR, TRANSACTION)
def sanitize_http_response_cookies(client, event):
    """
    Sanitizes the set-cookie header of the response
    :param client: an ElasticAPM client
    :param event: a transaction or error event
    :return: The modified event
    """
    try:
        cookie_string = event["context"]["response"]["headers"]["set-cookie"]
        event["context"]["response"]["headers"]["set-cookie"] = _sanitize_string(cookie_string, ";", "=")
    except (KeyError, TypeError):
        pass
    return event


@for_events(ERROR, TRANSACTION)
def sanitize_http_headers(client, event):
    """
    Sanitizes http request/response headers

    :param client: an ElasticAPM client
    :param event: a transaction or error event
    :return: The modified event
    """
    # request headers
    try:
        headers = event["context"]["request"]["headers"]
        event["context"]["request"]["headers"] = varmap(_sanitize, headers)
    except (KeyError, TypeError):
        pass

    # response headers
    try:
        headers = event["context"]["response"]["headers"]
        event["context"]["response"]["headers"] = varmap(_sanitize, headers)
    except (KeyError, TypeError):
        pass

    return event


@for_events(ERROR, TRANSACTION)
def sanitize_http_wsgi_env(client, event):
    """
    Sanitizes WSGI environment variables

    :param client: an ElasticAPM client
    :param event: a transaction or error event
    :return: The modified event
    """
    try:
        env = event["context"]["request"]["env"]
        event["context"]["request"]["env"] = varmap(_sanitize, env)
    except (KeyError, TypeError):
        pass
    return event


@for_events(ERROR, TRANSACTION)
def sanitize_http_request_querystring(client, event):
    """
    Sanitizes http request query string

    :param client: an ElasticAPM client
    :param event: a transaction or error event
    :return: The modified event
    """
    try:
        query_string = force_text(event["context"]["request"]["url"]["search"], errors="replace")
    except (KeyError, TypeError):
        return event
    if "=" in query_string:
        sanitized_query_string = _sanitize_string(query_string, "&", "=")
        full_url = event["context"]["request"]["url"]["full"]
        event["context"]["request"]["url"]["search"] = sanitized_query_string
        event["context"]["request"]["url"]["full"] = full_url.replace(query_string, sanitized_query_string)
    return event


@for_events(ERROR, TRANSACTION)
def sanitize_http_request_body(client, event):
    """
    Sanitizes http request body. This only works if the request body
    is a query-encoded string. Other types (e.g. JSON) are not handled by
    this sanitizer.

    :param client: an ElasticAPM client
    :param event: a transaction or error event
    :return: The modified event
    """
    try:
        body = force_text(event["context"]["request"]["body"], errors="replace")
    except (KeyError, TypeError):
        return event
    if "=" in body:
        sanitized_query_string = _sanitize_string(body, "&", "=")
        event["context"]["request"]["body"] = sanitized_query_string
    return event


@for_events(ERROR, SPAN)
def mark_in_app_frames(client, event):
    warnings.warn(
        "The mark_in_app_frames processor is deprecated and can be removed from your PROCESSORS setting",
        DeprecationWarning,
    )
    return event


def _sanitize(key, value):
    if value is None:
        return

    if isinstance(value, compat.string_types) and any(pattern.match(value) for pattern in SANITIZE_VALUE_PATTERNS):
        return MASK

    if not key:  # key can be a NoneType
        return value

    key = key.lower()
    for field in SANITIZE_FIELD_NAMES:
        if field in key:
            # store mask as a fixed length for security
            return MASK
    return value


def _sanitize_string(unsanitized, itemsep, kvsep):
    """
    sanitizes a string that contains multiple key/value items
    :param unsanitized: the unsanitized string
    :param itemsep: string that separates items
    :param kvsep: string that separates key from value
    :return: a sanitized string
    """
    sanitized = []
    kvs = unsanitized.split(itemsep)
    for kv in kvs:
        kv = kv.split(kvsep)
        if len(kv) == 2:
            sanitized.append((kv[0], _sanitize(kv[0], kv[1])))
        else:
            sanitized.append(kv)
    return itemsep.join(kvsep.join(kv) for kv in sanitized)


def _process_stack_frames(event, func):
    if "stacktrace" in event:
        for frame in event["stacktrace"]:
            func(frame)
    # an error can have two stacktraces, one in "exception", one in "log"
    if "exception" in event and "stacktrace" in event["exception"]:
        for frame in event["exception"]["stacktrace"]:
            func(frame)
    if "log" in event and "stacktrace" in event["log"]:
        for frame in event["log"]["stacktrace"]:
            func(frame)
    return event
