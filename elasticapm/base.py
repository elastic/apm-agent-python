"""
elasticapm.base
~~~~~~~~~~

:copyright: (c) 2011-2017 Elasticsearch

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

import datetime
import logging
import os
import platform
import socket
import sys
import time
import uuid
import warnings
import zlib

import elasticapm
from elasticapm.conf import defaults
from elasticapm.traces import TransactionsStore, get_transaction
from elasticapm.transport.base import TransportException
from elasticapm.utils import json_encoder as json
from elasticapm.utils import is_master_process, six, stacks, varmap
from elasticapm.utils.compat import atexit_register, urlparse
from elasticapm.utils.deprecation import deprecated
from elasticapm.utils.encoding import shorten, transform
from elasticapm.utils.module_import import import_string
from elasticapm.utils.stacks import get_culprit, iter_stack_frames

__all__ = ('Client',)


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
    The base ElasticAPM client, which handles communication over the
    HTTP API to the APM Server.

    Will read default configuration from the environment variable
    ``ELASTICAPM_APP_NAME`` and ``ELASTICAPM_SECRET_TOKEN``
    if available. ::

    >>> from elasticapm import Client

    >>> # Read configuration from environment
    >>> client = Client()

    >>> # Configure the client manually
    >>> client = Client(
    >>>     include_paths=['my.package'],
    >>>     app_name='app_name',
    >>>     secret_token='secret_token',
    >>> )

    >>> # Record an exception
    >>> try:
    >>>     1/0
    >>> except ZeroDivisionError:
    >>>     ident = client.get_ident(client.capture_exception())
    >>>     print ("Exception caught; reference is %%s" %% ident)
    """
    logger = logging.getLogger('elasticapm')
    protocol_version = '1.0'

    environment_config_map = {
        'app_name': 'ELASTICAPM_APP_NAME',
        'secret_token': 'ELASTICAPM_SECRET_TOKEN',
        'git_ref': 'ELASTICAPM_GIT_REF',
        'app_version': 'ELASTICAPM_APP_VERSION',
    }

    def __init__(self, app_name=None, secret_token=None,
                 transport_class=None, include_paths=None, exclude_paths=None,
                 timeout=None, hostname=None, auto_log_stacks=None,
                 string_max_length=None, list_max_length=None, processors=None,
                 filter_exception_types=None, servers=None,
                 async_mode=None, traces_send_freq_secs=None,
                 transactions_ignore_patterns=None, git_ref=None,
                 app_version=None,
                 **kwargs):
        self.app_name = self.secret_token = self.git_ref = self.app_version = None
        # configure loggers first
        cls = self.__class__
        self.logger = logging.getLogger('%s.%s' % (cls.__module__, cls.__name__))
        self.error_logger = logging.getLogger('elasticapm.errors')
        self.state = ClientState()
        self._configure(app_name=app_name,
                        secret_token=secret_token, git_ref=git_ref,
                        app_version=app_version)
        self.servers = servers or defaults.SERVERS
        self.async_mode = (async_mode is True
                           or (defaults.ASYNC_MODE and async_mode is not False))
        if not transport_class:
            transport_class = (defaults.ASYNC_TRANSPORT_CLASS
                               if self.async_mode
                               else defaults.SYNC_TRANSPORT_CLASS)
        self._transport_class = import_string(transport_class)
        self._transports = {}

        # servers may be set to a NoneType (for Django)
        if self.servers and not (self.app_name and self.secret_token):
            msg = 'Missing configuration for ElasticAPM client. Please see documentation.'
            self.logger.info(msg)

        self.is_send_disabled = (
            os.environ.get('ELASTICAPM_DISABLE_SEND', '').lower() in ('1', 'true')
        )
        if self.is_send_disabled:
            self.logger.info(
                'Not sending any data to APM Server due to ELASTICAPM_DISABLE_SEND '
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

        self.filter_exception_types_dict = {}
        for exc_to_filter in (filter_exception_types or []):
            exc_to_filter_type = exc_to_filter.split(".")[-1]
            exc_to_filter_module = ".".join(exc_to_filter.split(".")[:-1])
            self.filter_exception_types_dict[exc_to_filter_type] = exc_to_filter_module

        if processors is None:
            self.processors = defaults.PROCESSORS
        else:
            self.processors = processors
        self.processors = [import_string(p) for p in self.processors]

        self.instrumentation_store = TransactionsStore(
            lambda: self.get_stack_info_for_trace(iter_stack_frames(), False),
            self.traces_send_freq_secs,
            transactions_ignore_patterns
        )
        atexit_register(self.close)

    def _configure(self, **kwargs):
        """
        Configures this instance based on kwargs, or environment variables.
        The former take precedence.
        """
        for attr_name, value in kwargs.items():
            if value is None and (attr_name in self.environment_config_map
                                  and self.environment_config_map[attr_name] in os.environ):
                self.logger.info("Configuring elasticapm.%s from environment variable '%s'",
                                 attr_name, self.environment_config_map[attr_name])
                value = os.environ[self.environment_config_map[attr_name]]
            setattr(self, attr_name, six.text_type(value))

    def get_ident(self, result):
        """
        Returns a searchable string representing a message.

        >>> result = client.process(**kwargs)
        >>> ident = client.get_ident(result)
        """
        return result

    def get_handler(self, name):
        return import_string(name)

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
        if 'context' not in data:
            data['context'] = context = {}
        else:
            context = data['context']

        # if '.' not in event_type:
        # Assume it's a builtin
        event_type = 'elasticapm.events.%s' % event_type

        handler = self.get_handler(event_type)
        result = handler.capture(self, data=data, **kwargs)
        if self._filter_exception_type(result):
            return
        # data (explicit) culprit takes over auto event detection
        culprit = result.pop('culprit', None)
        if data.get('culprit'):
            culprit = data['culprit']

        for k, v in six.iteritems(result):
            if k not in data:
                data[k] = v

        log = data.get('log', {})
        if stack and 'stacktrace' not in log:
            if stack is True:
                frames = iter_stack_frames()
            else:
                frames = stack
            frames = varmap(lambda k, v: shorten(
                v,
                string_length=self.string_max_length,
                list_length=self.list_max_length
            ), stacks.get_stack_info(frames))
            log['stacktrace'] = frames

        if 'stacktrace' in log and not culprit:
            culprit = get_culprit(
                log['stacktrace'],
                self.include_paths, self.exclude_paths
            )

        if 'level' in log and isinstance(log['level'], six.integer_types):
            log['level'] = logging.getLevelName(log['level']).lower()

        if log:
            data['log'] = log

        if culprit:
            data['culprit'] = culprit

        context['custom'] = extra

        # Run the data through processors
        for processor in self.processors:
            data = processor(self, data)

        # Make sure all data is coerced
        data = transform(data)

        data.update({
            'timestamp':  date.strftime(defaults.TIMESTAMP_FORMAT),
        })

        return self.build_msg({'errors': [data]})

    def build_msg(self, data=None, **kwargs):
        data = data or {}
        data['app'] = self.get_app_info()
        data['system'] = self.get_system_info()
        data.update(**kwargs)
        return data

    def capture(self, event_type, data=None, date=None,
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

        if data:
            servers = [server + defaults.ERROR_API_PATH for server in self.servers]
            self.send(servers=servers, **data)
            return data['errors'][0]['id']

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
        except Exception:
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
                if exc_module:
                    exc_name = '%s.%s' % (exc_module, exc_type)
                else:
                    exc_name = exc_type
                self.logger.info(
                    'Ignored %s exception due to exception type filter',
                    exc_name
                )
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
            warnings.warn('elasticapm client has no remote servers configured')
            return

        if not auth_header:
            if not secret_token:
                secret_token = self.secret_token

            auth_header = "Bearer %s" % (secret_token)

        for url in servers:
            headers = {
                'Authorization': auth_header,
                'Content-Type': 'application/json',
                'Content-Encoding': 'deflate',
                'User-Agent': 'elasticapm-python/%s' % elasticapm.VERSION,
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

    def begin_transaction(self, transaction_type):
        """Register the start of a transaction on the client

        'kind' should follow the convention of '<transaction-kind>.<provider>'
        e.g. 'web.django', 'task.celery'.
        """
        self.instrumentation_store.begin_transaction(transaction_type)

    def end_transaction(self, name, status_code=None):
        self.instrumentation_store.end_transaction(status_code, name)
        if self.instrumentation_store.should_collect():
            self._traces_collect()

    def set_transaction_name(self, name):
        transaction = get_transaction()
        if not transaction:
            return
        transaction.name = name

    def set_transaction_extra_data(self, data, _key=None):
        transaction = get_transaction()
        if not transaction:
            return
        if not _key:
            _key = 'extra'
        transaction.extra[_key] = data

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

    def handle_transport_fail(self, exception=None, **kwargs):
        """
        Failure handler called by the transport
        """
        if isinstance(exception, TransportException):
            message = self._get_log_message(exception.data)
            self.error_logger.error(exception.args[0])
        else:
            # stdlib exception
            message = str(exception)
        self.error_logger.error(
            'Failed to submit message: %r',
            message,
            exc_info=getattr(exception, 'print_trace', True)
        )
        self.state.set_fail()

    def _traces_collect(self):
        transactions = self.instrumentation_store.get_all()
        if not transactions:
            return

        data = self.build_msg({
            'transactions': transactions,
        })
        api_path = defaults.TRANSACTIONS_API_PATH

        self.send(servers=[server + api_path for server in self.servers], **data)

    def get_app_info(self):
        language_version = platform.python_version()
        if hasattr(sys, 'pypy_version_info'):
            runtime_version = '.'.join(map(str, sys.pypy_version_info[:3]))
        else:
            runtime_version = language_version
        return {
            'name': self.app_name,
            'version': self.app_version,
            'agent': {
                'name': 'elasticapm-python',
                'version': elasticapm.VERSION,
            },
            'argv': sys.argv,
            'framework': {
                'name': getattr(self, '_framework', None),
                'version': getattr(self, '_framework_version', None),
            },
            'git_ref': self.git_ref,
            'language': {
                'name': 'python',
                'version': platform.python_version(),
            },
            'pid': os.getpid(),
            'process_title': None,
            'runtime': {
                'name': platform.python_implementation(),
                'version': runtime_version,
            }
        }

    def get_system_info(self):
        return {
            'hostname': socket.gethostname(),
            'architecture': platform.machine(),
            'platform': platform.system().lower(),
        }

class DummyClient(Client):
    """Sends messages into an empty void"""
    def send(self, **kwargs):
        return None
