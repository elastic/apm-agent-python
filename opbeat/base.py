"""
opbeat.base
~~~~~~~~~~

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

import datetime
import logging
import os
import platform
import sys
import time
import uuid
import warnings
import zlib

import opbeat
from opbeat.conf import defaults
from opbeat.traces import RequestsStore
from opbeat.utils import opbeat_json as json
from opbeat.utils import is_master_process, six, stacks, varmap
from opbeat.utils.compat import atexit_register, urlparse
from opbeat.utils.deprecation import deprecated
from opbeat.utils.encoding import shorten, transform
from opbeat.utils.module_import import import_string
from opbeat.utils.stacks import get_culprit, iter_stack_frames

__all__ = ('Client',)


class ModuleProxyCache(dict):
    def __missing__(self, key):
        module, class_name = key.rsplit('.', 1)

        handler = getattr(__import__(module, {},
                {}, [class_name]), class_name)

        self[key] = handler

        return handler


class ClientState(object):
    ONLINE = 1
    ERROR = 0

    def __init__(self):
        self.status = self.ONLINE
        self.last_check = None
        self.retry_number = 0

    def should_try(self):
        if self.status == self.ONLINE:
            return True

        interval = min(self.retry_number, 6) ** 2

        if time.time() - self.last_check > interval:
            return True

        return False

    def set_fail(self):
        self.status = self.ERROR
        self.retry_number += 1
        self.last_check = time.time()

    def set_success(self):
        self.status = self.ONLINE
        self.last_check = None
        self.retry_number = 0

    def did_fail(self):
        return self.status == self.ERROR


class Client(object):
    """
    The base opbeat client, which handles communication over the
    HTTP API to Opbeat servers.

    Will read default configuration from the environment variable
    ``OPBEAT_ORGANIZATION_ID``, ``OPBEAT_APP_ID`` and ``OPBEAT_SECRET_TOKEN``
    if available. ::

    >>> from opbeat import Client

    >>> # Read configuration from environment
    >>> client = Client()

    >>> # Configure the client manually
    >>> client = Client(
    >>>     include_paths=['my.package'],
    >>>     organization_id='org_id',
    >>>     app_id='app_id',
    >>>     secret_token='secret_token',
    >>> )

    >>> # Record an exception
    >>> try:
    >>>     1/0
    >>> except ZeroDivisionError:
    >>>     ident = client.get_ident(client.capture_exception())
    >>>     print ("Exception caught; reference is %%s" %% ident)
    """
    logger = logging.getLogger('opbeat')
    protocol_version = '1.0'

    def __init__(self, organization_id=None, app_id=None, secret_token=None,
                 transport_class=None, include_paths=None, exclude_paths=None,
                 timeout=None, hostname=None, auto_log_stacks=None, key=None,
                 string_max_length=None, list_max_length=None, processors=None,
                 filter_exception_types=None, servers=None, api_path=None,
                 async=None, async_mode=None, traces_send_freq_secs=None,
                 transactions_ignore_patterns=None, framework_version='',
                 **kwargs):
        # configure loggers first
        cls = self.__class__
        self.logger = logging.getLogger('%s.%s' % (cls.__module__,
            cls.__name__))
        self.error_logger = logging.getLogger('opbeat.errors')
        self.state = ClientState()

        if organization_id is None and os.environ.get('OPBEAT_ORGANIZATION_ID'):
            msg = "Configuring opbeat from environment variable 'OPBEAT_ORGANIZATION_ID'"
            self.logger.info(msg)
            organization_id = os.environ['OPBEAT_ORGANIZATION_ID']

        if app_id is None and os.environ.get('OPBEAT_APP_ID'):
            msg = "Configuring opbeat from environment variable 'OPBEAT_APP_ID'"
            self.logger.info(msg)
            app_id = os.environ['OPBEAT_APP_ID']

        if secret_token is None and os.environ.get('OPBEAT_SECRET_TOKEN'):
            msg = "Configuring opbeat from environment variable 'OPBEAT_SECRET_TOKEN'"
            self.logger.info(msg)
            secret_token = os.environ['OPBEAT_SECRET_TOKEN']

        self.servers = servers or defaults.SERVERS
        if async is not None and async_mode is None:
            warnings.warn(
                'Usage of "async" argument is deprecated. Use "async_mode"',
                category=DeprecationWarning,
                stacklevel=2,
            )
            async_mode = async
        self.async_mode = (async_mode is True
                           or (defaults.ASYNC_MODE and async_mode is not False))
        if not transport_class:
            transport_class = (defaults.ASYNC_TRANSPORT_CLASS
                               if self.async_mode
                               else defaults.SYNC_TRANSPORT_CLASS)
        self._transport_class = import_string(transport_class)
        self._transports = {}

        # servers may be set to a NoneType (for Django)
        if self.servers and not (organization_id and app_id and secret_token):
            msg = 'Missing configuration for Opbeat client. Please see documentation.'
            self.logger.info(msg)

        self.is_send_disabled = (
            os.environ.get('OPBEAT_DISABLE_SEND', '').lower() in ('1', 'true')
        )
        if self.is_send_disabled:
            self.logger.info(
                'Not sending any data to Opbeat due to OPBEAT_DISABLE_SEND '
                'environment variable'
            )

        self.include_paths = set(include_paths or defaults.INCLUDE_PATHS)
        self.exclude_paths = set(exclude_paths or defaults.EXCLUDE_PATHS)
        self.timeout = int(timeout or defaults.TIMEOUT)
        self.hostname = six.text_type(hostname or defaults.HOSTNAME)
        self.auto_log_stacks = bool(auto_log_stacks or
                                    defaults.AUTO_LOG_STACKS)

        self.string_max_length = int(string_max_length or
                                     defaults.MAX_LENGTH_STRING)
        self.list_max_length = int(list_max_length or defaults.MAX_LENGTH_LIST)
        self.traces_send_freq_secs = (traces_send_freq_secs or
                                      defaults.TRACES_SEND_FREQ_SECS)

        self.organization_id = six.text_type(organization_id)
        self.app_id = six.text_type(app_id)
        self.secret_token = six.text_type(secret_token)

        self.filter_exception_types_dict = {}
        for exc_to_filter in (filter_exception_types or []):
            exc_to_filter_type = exc_to_filter.split(".")[-1]
            exc_to_filter_module = ".".join(exc_to_filter.split(".")[:-1])
            self.filter_exception_types_dict[exc_to_filter_type] = exc_to_filter_module

        if processors is None:
            self.processors = defaults.PROCESSORS
        else:
            self.processors = processors

        self._framework_version = framework_version

        self.module_cache = ModuleProxyCache()

        self.instrumentation_store = RequestsStore(
            lambda: self.get_stack_info_for_trace(iter_stack_frames(), False),
            self.traces_send_freq_secs,
            transactions_ignore_patterns
        )
        atexit_register(self.close)

    def get_processors(self):
        for processor in self.processors:
            yield self.module_cache[processor](self)

    def get_ident(self, result):
        """
        Returns a searchable string representing a message.

        >>> result = client.process(**kwargs)
        >>> ident = client.get_ident(result)
        """
        return result

    def get_handler(self, name):
        return self.module_cache[name](self)

    def get_stack_info_for_trace(self, frames, extended=True):
        """Overrideable in derived clients to add frames/info, e.g. templates

        4.0: Use for error frames too.
        """
        return stacks.get_stack_info(frames, extended)

    def build_msg_for_logging(self, event_type, data=None, date=None,
                              extra=None, stack=None,
                              **kwargs):
        """
        Captures, processes and serializes an event into a dict object
        """
        # create ID client-side so that it can be passed to application
        event_id = uuid.uuid4().hex

        if data is None:
            data = {}
        if extra is None:
            extra = {}
        if not date:
            date = datetime.datetime.utcnow()
        if stack is None:
            stack = self.auto_log_stacks

        self.build_msg(data=data)

        # if '.' not in event_type:
        # Assume it's a builtin
        event_type = 'opbeat.events.%s' % event_type

        handler = self.get_handler(event_type)

        result = handler.capture(**kwargs)

        # data (explicit) culprit takes over auto event detection
        culprit = result.pop('culprit', None)
        if data.get('culprit'):
            culprit = data['culprit']

        for k, v in six.iteritems(result):
            if k not in data:
                data[k] = v

        if stack and 'stacktrace' not in data:
            if stack is True:
                frames = iter_stack_frames()
            else:
                frames = stack

            data.update({
                'stacktrace': {
                    'frames': varmap(lambda k, v: shorten(v,
                        string_length=self.string_max_length,
                        list_length=self.list_max_length),
                                     stacks.get_stack_info(frames))
                },
            })

        if 'stacktrace' in data and not culprit:
            culprit = get_culprit(
                data['stacktrace']['frames'],
                self.include_paths, self.exclude_paths
            )

        if not data.get('level'):
            data['level'] = 'error'

        if isinstance( data['level'], six.integer_types):
            data['level'] = logging.getLevelName(data['level']).lower()

        data.setdefault('extra', {})

        # Shorten lists/strings
        for k, v in six.iteritems(extra):
            data['extra'][k] = shorten(v, string_length=self.string_max_length,
                    list_length=self.list_max_length)

        if culprit:
            data['culprit'] = culprit

        # Run the data through processors
        for processor in self.get_processors():
            data.update(processor.process(data))

        # Make sure all data is coerced
        data = transform(data)

        if 'message' not in data:
            data['message'] = handler.to_string(data)

        # Make sure certain values are not too long
        for v in defaults.MAX_LENGTH_VALUES:
            if v in data:
                data[v] = shorten(data[v],
                            string_length=defaults.MAX_LENGTH_VALUES[v]
                          )

        data.update({
            'timestamp':  date,
            # 'time_spent': time_spent,
            'client_supplied_id': event_id,
        })

        return data

    def build_msg(self, data=None, **kwargs):
        data.setdefault('machine', {'hostname': self.hostname})
        data.setdefault('organization_id', self.organization_id)
        data.setdefault('app_id', self.app_id)
        data.setdefault('secret_token', self.secret_token)
        return data

    def capture(self, event_type, data=None, date=None, api_path=None,
                extra=None, stack=None, **kwargs):
        """
        Captures and processes an event and pipes it off to Client.send.

        To use structured data (interfaces) with capture:

        >>> client.capture('Message', message='foo', data={
        >>>     'http': {
        >>>         'url': '...',
        >>>         'data': {},
        >>>         'query_string': '...',
        >>>         'method': 'POST',
        >>>     },
        >>>     'logger': 'logger.name',
        >>>     'site': 'site.name',
        >>> }, extra={
        >>>     'key': 'value',
        >>> })

        The finalized ``data`` structure contains the following (some optional)
        builtin values:

        >>> {
        >>>     # the culprit and version information
        >>>     'culprit': 'full.module.name', # or /arbitrary/path
        >>>
        >>>     # arbitrary data provided by user
        >>>     'extra': {
        >>>         'key': 'value',
        >>>     }
        >>> }

        :param event_type: the module path to the Event class. Builtins can use
                           shorthand class notation and exclude the full module
                           path.
        :param data: the data base
        :param date: the datetime of this event
        :param extra: a dictionary of additional standard metadata
        :return: a 32-length string identifying this event
        """

        data = self.build_msg_for_logging(event_type, data, date,
                                          extra, stack, **kwargs)

        if not api_path:
            api_path = defaults.ERROR_API_PATH.format(
                data['organization_id'],
                data['app_id']
            )

        data['servers'] = [server+api_path for server in self.servers]
        self.send(**data)

        return data['client_supplied_id']

    def _send_remote(self, url, data, headers=None):
        if headers is None:
            headers = {}
        parsed = urlparse.urlparse(url)
        transport = self._get_transport(parsed)
        if transport.async_mode:
            transport.send_async(
                data, headers,
                success_callback=self.handle_transport_success,
                fail_callback=self.handle_transport_fail
            )
        else:
            url = transport.send(data, headers, timeout=self.timeout)
            self.handle_transport_success(url=url)

    def _get_log_message(self, data):
        # decode message so we can show the actual event
        try:
            data = self.decode(data)
        except:
            message = '<failed decoding data>'
        else:
            message = data.pop('message', '<no message value>')
        return message

    def _get_transport(self, parsed_url):
        if self.async_mode and is_master_process():
            # when in the master process, always use SYNC mode. This avoids
            # the danger of being forked into an inconsistent threading state
            self.logger.info('Sending message synchronously while in master '
                             'process. PID: %s', os.getpid())
            return import_string(defaults.SYNC_TRANSPORT_CLASS)(parsed_url)
        if parsed_url not in self._transports:
            self._transports[parsed_url] = self._transport_class(parsed_url)
        return self._transports[parsed_url]

    def _filter_exception_type(self, data):
        exception = data.get('exception')
        if not exception:
            return False

        exc_type = exception.get('type')
        exc_module = exception.get('module')
        if exc_module == 'None':
            exc_module = None

        if exc_type in self.filter_exception_types_dict:
            exc_to_filter_module = self.filter_exception_types_dict[exc_type]
            if not exc_to_filter_module or exc_to_filter_module == exc_module:
                    return True

        return False

    def send_remote(self, url, data, headers=None):
        if not self.state.should_try():
            message = self._get_log_message(data)
            self.error_logger.error(message)
            return
        try:
            self._send_remote(url=url, data=data, headers=headers)
        except Exception as e:
            self.handle_transport_fail(exception=e)

    def send(self, secret_token=None, auth_header=None,
             servers=None, **data):
        """
        Serializes the message and passes the payload onto ``send_encoded``.
        """

        if self.is_send_disabled or self._filter_exception_type(data):
            return

        message = self.encode(data)

        return self.send_encoded(message,
                                 secret_token=secret_token,
                                 auth_header=auth_header,
                                 servers=servers)

    def send_encoded(self, message, secret_token, auth_header=None,
                     servers=None, **kwargs):
        """
        Given an already serialized message, signs the message and passes the
        payload off to ``send_remote`` for each server specified in the servers
        configuration.
        """
        servers = servers or self.servers
        if not servers:
            warnings.warn('opbeat client has no remote servers configured')
            return

        if not auth_header:
            if not secret_token:
                secret_token = self.secret_token

            auth_header = "Bearer %s" % (secret_token)

        for url in servers:
            headers = {
                'Authorization': auth_header,
                'Content-Type': 'application/octet-stream',
                'User-Agent': 'opbeat-python/%s' % opbeat.VERSION,
                'X-Opbeat-Platform': self.get_platform_info()
            }

            self.send_remote(url=url, data=message, headers=headers)

    def encode(self, data):
        """
        Serializes ``data`` into a raw string.
        """
        return zlib.compress(json.dumps(data).encode('utf8'))

    def decode(self, data):
        """
        Unserializes a string, ``data``.
        """
        return json.loads(zlib.decompress(data).decode('utf8'))

    def capture_message(self, message, **kwargs):
        """
        Creates an event from ``message``.

        >>> client.capture_message('My event just happened!')
        """
        return self.capture('Message', message=message, **kwargs)

    @deprecated(alternative="capture_message()")
    def captureMessage(self, message, **kwargs):
        """
        Deprecated
        :param message:
        :type message:
        :param kwargs:
        :type kwargs:
        :return:
        :rtype:
        """
        self.capture_message(message, **kwargs)

    def capture_exception(self, exc_info=None, **kwargs):
        """
        Creates an event from an exception.

        >>> try:
        >>>     exc_info = sys.exc_info()
        >>>     client.capture_exception(exc_info)
        >>> finally:
        >>>     del exc_info

        If exc_info is not provided, or is set to True, then this method will
        perform the ``exc_info = sys.exc_info()`` and the requisite clean-up
        for you.
        """
        return self.capture('Exception', exc_info=exc_info, **kwargs)

    @deprecated(alternative="capture_exception()")
    def captureException(self, exc_info=None, **kwargs):
        """
        Deprecated
        """
        self.capture_exception(exc_info, **kwargs)

    def capture_query(self, query, params=(), engine=None, **kwargs):
        """
        Creates an event for a SQL query.

        >>> client.capture_query('SELECT * FROM foo')
        """
        return self.capture('Query', query=query, params=params, engine=engine,
                            **kwargs)

    @deprecated(alternative="capture_query()")
    def captureQuery(self, *args, **kwargs):
        """
        Deprecated
        """
        self.capture_query(*args, **kwargs)

    def begin_transaction(self, kind):
        """Register the start of a transaction on the client

        'kind' should follow the convention of '<transaction-kind>.<provider>'
        e.g. 'web.django', 'task.celery'.
        """
        self.instrumentation_store.transaction_start(self, kind)

    def end_transaction(self, name, status_code=None):
        self.instrumentation_store.transaction_end(status_code, name)
        if self.instrumentation_store.should_collect():
            self._traces_collect()

    def close(self):
        self._traces_collect()
        for url, transport in self._transports.items():
            transport.close()

    def handle_transport_success(self, **kwargs):
        """
        Success handler called by the transport
        """
        if kwargs.get('url'):
            self.logger.info('Logged error at ' + kwargs['url'])
        self.state.set_success()

    def handle_transport_fail(self, **kwargs):
        """
        Failure handler called by the transport
        """
        exception = kwargs.get('exception')
        message = self._get_log_message(exception.data)
        self.error_logger.error(exception.args[0])
        self.error_logger.error(
            'Failed to submit message: %r',
            message,
            exc_info=getattr(exception, 'print_trace', True)
        )
        self.state.set_fail()

    def _traces_collect(self):
        transactions, traces = self.instrumentation_store.get_all()
        if not transactions or not traces:
            return

        data = self.build_msg({
            'transactions': transactions,
            'traces': traces,
        })
        api_path = defaults.TRANSACTIONS_API_PATH.format(
            self.organization_id,
            self.app_id,
        )

        data['servers'] = [server + api_path for server in self.servers]
        self.send(**data)

    def get_platform_info(self):
        platform_bits = {'lang': 'python/' + platform.python_version()}
        implementation = platform.python_implementation()
        if implementation == 'PyPy':
            implementation += '/' + '.'.join(map(str, sys.pypy_version_info[:3]))
        platform_bits['platform'] = implementation
        if self._framework_version:
            platform_bits['framework'] = self._framework_version
        return ' '.join('%s=%s' % item for item in platform_bits.items())


class DummyClient(Client):
    """Sends messages into an empty void"""
    def send(self, **kwargs):
        return None
