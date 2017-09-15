"""
elasticapm.core.processors
~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2017 Elasticsearch

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

import re

from elasticapm.utils import compat, varmap
from elasticapm.utils.encoding import force_text

MASK = 8 * '*'

SANITIZE_FIELD_NAMES = frozenset([
    'password',
    'secret',
    'passwd',
    'token',
    'api_key',
    'access_token',
    'sessionid',
])

SANITIZE_VALUE_PATTERNS = [
    re.compile(r'^[- \d]{16,19}$'),  # credit card numbers, with or without spacers
]


def remove_http_request_body(client, event):
    """
    Removes request.body from context

    :param client: an ElasticAPM client
    :param event: a transaction or error event
    :return: The modified event
    """
    if 'context' in event and 'request' in event['context']:
        event['context']['request'].pop('body', None)
    return event


def remove_stacktrace_locals(client, event):
    """
    Removes local variables from any frames.

    :param client: an ElasticAPM client
    :param event: a transaction or error event
    :return: The modified event
    """
    func = lambda frame: frame.pop('vars', None)
    return _process_stack_frames(event, func)


def sanitize_stacktrace_locals(client, event):
    """
    Sanitizes local variables in all frames

    :param client: an ElasticAPM client
    :param event: a transaction or error event
    :return: The modified event
    """
    def func(frame):
        if 'vars' in frame:
            frame['vars'] = varmap(_sanitize, frame['vars'])

    return _process_stack_frames(event, func)


def sanitize_http_request_cookies(client, event):
    """
    Sanitizes http request cookies

    :param client: an ElasticAPM client
    :param event: a transaction or error event
    :return: The modified event
    """

    # sanitize request.cookies dict
    try:
        cookies = event['context']['request']['cookies']
        event['context']['request']['cookies'] = varmap(_sanitize, cookies)
    except (KeyError, TypeError):
        pass

    # sanitize request.header.cookie string
    try:
        cookie_string = event['context']['request']['headers']['cookie']
        event['context']['request']['headers']['cookie'] = _sanitize_string(
            cookie_string, '; ', '='
        )
    except (KeyError, TypeError):
        pass
    return event


def sanitize_http_headers(client, event):
    """
    Sanitizes http request/response headers

    :param client: an ElasticAPM client
    :param event: a transaction or error event
    :return: The modified event
    """
    # request headers
    try:
        headers = event['context']['request']['headers']
        event['context']['request']['headers'] = varmap(_sanitize, headers)
    except (KeyError, TypeError):
        pass

    # response headers
    try:
        headers = event['context']['response']['headers']
        event['context']['response']['headers'] = varmap(_sanitize, headers)
    except (KeyError, TypeError):
        pass

    return event


def sanitize_http_wsgi_env(client, event):
    """
    Sanitizes WSGI environment variables

    :param client: an ElasticAPM client
    :param event: a transaction or error event
    :return: The modified event
    """
    try:
        env = event['context']['request']['env']
        event['context']['request']['env'] = varmap(_sanitize, env)
    except (KeyError, TypeError):
        pass
    return event


def sanitize_http_request_querystring(client, event):
    """
    Sanitizes http request query string

    :param client: an ElasticAPM client
    :param event: a transaction or error event
    :return: The modified event
    """
    try:
        query_string = force_text(
            event['context']['request']['url']['search'],
            errors='replace'
        )
    except (KeyError, TypeError):
        return event
    if '=' in query_string:
        sanitized_query_string = _sanitize_string(query_string, '&', '=')
        raw = event['context']['request']['url']['raw']
        event['context']['request']['url']['search'] = sanitized_query_string
        event['context']['request']['url']['raw'] = raw.replace(
            query_string,
            sanitized_query_string
        )
    return event


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
        body = force_text(
            event['context']['request']['body'],
            errors='replace'
        )
    except (KeyError, TypeError):
        return event
    if '=' in body:
        sanitized_query_string = _sanitize_string(body, '&', '=')
        event['context']['request']['body'] = sanitized_query_string
    return event


def mark_in_app_frames(client, event):
    """
    Marks frames as "in app" if the module matches any entries in config.include_paths and
    doesn't match any entries in config.exclude_paths.

    :param client: an ElasticAPM client
    :param event: a transaction or error event
    :return: The modified event
    """
    include = client.config.include_paths or []
    exclude = client.config.exclude_paths or []

    def _is_in_app(frame):
        if 'module' not in frame:
            return
        mod = frame['module']
        frame['in_app'] = mod and bool(
            any(mod.startswith(path + '.') or mod == path for path in include) and
            not any(mod.startswith(path + '.') or mod == path for path in exclude)
        )

    _process_stack_frames(event, _is_in_app)
    return event


def _sanitize(key, value):
    if value is None:
        return

    if isinstance(value, compat.string_types) and any(
            pattern.match(value) for pattern in SANITIZE_VALUE_PATTERNS):
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
    if 'traces' in event:
        # every trace can have a stack trace
        for trace in event['traces']:
            if 'stacktrace' in trace:
                for frame in trace['stacktrace']:
                    func(frame)
    # an error can have two stacktraces, one in "exception", one in "log"
    if 'exception' in event and 'stacktrace' in event['exception']:
        for frame in event['exception']['stacktrace']:
            func(frame)
    if 'log' in event and 'stacktrace' in event['log']:
        for frame in event['log']['stacktrace']:
            func(frame)
    return event
