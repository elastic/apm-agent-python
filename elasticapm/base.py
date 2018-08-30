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
import threading
import time
import zlib
from copy import deepcopy

import elasticapm
from elasticapm.conf import Config, constants
from elasticapm.traces import TransactionsStore, get_transaction
from elasticapm.transport.base import TransportException
from elasticapm.utils import compat, is_master_process
from elasticapm.utils import json_encoder as json
from elasticapm.utils import stacks, varmap
from elasticapm.utils.encoding import keyword_field, shorten, transform
from elasticapm.utils.module_import import import_string

__all__ = ("Client",)


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
    ``ELASTIC_APM_APP_NAME`` and ``ELASTIC_APM_SECRET_TOKEN``
    if available. ::

    >>> from elasticapm import Client

    >>> # Read configuration from environment
    >>> client = Client()

    >>> # Configure the client manually
    >>> client = Client(
    >>>     include_paths=['my.package'],
    >>>     service_name='myapp',
    >>>     secret_token='secret_token',
    >>> )

    >>> # Record an exception
    >>> try:
    >>>     1/0
    >>> except ZeroDivisionError:
    >>>     ident = client.capture_exception()
    >>>     print ("Exception caught; reference is %%s" %% ident)
    """

    logger = logging.getLogger("elasticapm")

    def __init__(self, config=None, **inline):
        # configure loggers first
        cls = self.__class__
        self.logger = logging.getLogger("%s.%s" % (cls.__module__, cls.__name__))
        self.error_logger = logging.getLogger("elasticapm.errors")
        self.state = ClientState()

        self.transaction_store = None
        self.processors = []
        self.filter_exception_types_dict = {}
        self._send_timer = None
        self._transports = {}
        self._service_info = None

        self.config = Config(config, inline_dict=inline)
        if self.config.errors:
            for msg in self.config.errors.values():
                self.error_logger.error(msg)
            self.config.disable_send = True

        self._transport_class = import_string(self.config.transport_class)

        for exc_to_filter in self.config.filter_exception_types or []:
            exc_to_filter_type = exc_to_filter.split(".")[-1]
            exc_to_filter_module = ".".join(exc_to_filter.split(".")[:-1])
            self.filter_exception_types_dict[exc_to_filter_type] = exc_to_filter_module

        self.processors = [import_string(p) for p in self.config.processors] if self.config.processors else []

        if platform.python_implementation() == "PyPy":
            # PyPy introduces a `_functools.partial.__call__` frame due to our use
            # of `partial` in AbstractInstrumentedModule
            skip_modules = ("elasticapm.", "_functools")
        else:
            skip_modules = ("elasticapm.",)

        def frames_collector_func():
            return self._get_stack_info_for_trace(
                stacks.iter_stack_frames(skip_top_modules=skip_modules),
                library_frame_context_lines=self.config.source_lines_span_library_frames,
                in_app_frame_context_lines=self.config.source_lines_span_app_frames,
                with_locals=self.config.collect_local_variables in ("all", "transactions"),
                locals_processor_func=lambda local_var: varmap(
                    lambda k, v: shorten(
                        v,
                        list_length=self.config.local_var_list_max_length,
                        string_length=self.config.local_var_max_length,
                    ),
                    local_var,
                ),
            )

        self.transaction_store = TransactionsStore(
            frames_collector_func=frames_collector_func,
            collect_frequency=self.config.flush_interval,
            sample_rate=self.config.transaction_sample_rate,
            max_spans=self.config.transaction_max_spans,
            span_frames_min_duration=self.config.span_frames_min_duration_ms,
            max_queue_size=self.config.max_queue_size,
            ignore_patterns=self.config.transactions_ignore_patterns,
        )
        self.include_paths_re = stacks.get_path_regex(self.config.include_paths) if self.config.include_paths else None
        self.exclude_paths_re = stacks.get_path_regex(self.config.exclude_paths) if self.config.exclude_paths else None
        compat.atexit_register(self.close)

    def get_handler(self, name):
        return import_string(name)

    def capture(self, event_type, date=None, context=None, custom=None, stack=None, handled=True, **kwargs):
        """
        Captures and processes an event and pipes it off to Client.send.
        """
        if event_type == "Exception":
            # never gather log stack for exceptions
            stack = False
        data = self._build_msg_for_logging(
            event_type, date=date, context=context, custom=custom, stack=stack, handled=handled, **kwargs
        )

        if data:
            url = self.config.server_url + constants.ERROR_API_PATH
            self.send(url, **data)
            return data["errors"][0]["id"]

    def capture_message(self, message=None, param_message=None, **kwargs):
        """
        Creates an event from ``message``.

        >>> client.capture_message('My event just happened!')
        """
        return self.capture("Message", message=message, param_message=param_message, **kwargs)

    def capture_exception(self, exc_info=None, handled=True, **kwargs):
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
        return self.capture("Exception", exc_info=exc_info, handled=handled, **kwargs)

    def send(self, url, **data):
        """
        Encodes and sends data to remote URL using configured transport
        :param url: URL of endpoint
        :param data: dictionary of data to send
        """
        if self.config.disable_send or self._filter_exception_type(data):
            return

        payload = self.encode(data)

        headers = {
            "Content-Type": "application/json",
            "Content-Encoding": "deflate",
            "User-Agent": "elasticapm-python/%s" % elasticapm.VERSION,
        }

        if self.config.secret_token:
            headers["Authorization"] = "Bearer %s" % self.config.secret_token

        if not self.state.should_try():
            message = self._get_log_message(payload)
            self.error_logger.error(message)
            return
        try:
            self._send_remote(url=url, data=payload, headers=headers)
        except Exception as e:
            self.handle_transport_fail(exception=e)

    def encode(self, data):
        """
        Serializes ``data`` into a raw string.
        """
        return zlib.compress(json.dumps(data).encode("utf8"))

    def decode(self, data):
        """
        Unserializes a string, ``data``.
        """
        return json.loads(zlib.decompress(data).decode("utf8"))

    def begin_transaction(self, transaction_type):
        """Register the start of a transaction on the client
        """
        return self.transaction_store.begin_transaction(transaction_type)

    def end_transaction(self, name=None, result=""):
        transaction = self.transaction_store.end_transaction(result, name)
        if self.transaction_store.should_collect():
            self._collect_transactions()
        if not self._send_timer:
            # send first batch of data after config._wait_to_first_send
            self._start_send_timer(timeout=min(self.config._wait_to_first_send, self.config.flush_interval))
        return transaction

    def close(self):
        self._collect_transactions()
        if self._send_timer:
            self._stop_send_timer()
        for url, transport in list(self._transports.items()):
            transport.close()
            self._transports.pop(url)

    def handle_transport_success(self, **kwargs):
        """
        Success handler called by the transport
        """
        if kwargs.get("url"):
            self.logger.info("Logged error at " + kwargs["url"])
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
            "Failed to submit message: %r", message, exc_info=getattr(exception, "print_trace", True)
        )
        self.state.set_fail()

    def _collect_transactions(self):
        self._stop_send_timer()
        transactions = []
        if self.transaction_store:
            for transaction in self.transaction_store.get_all():
                for processor in self.processors:
                    transaction = processor(self, transaction)
                transactions.append(transaction)
        if not transactions:
            return

        data = self._build_msg({"transactions": transactions})

        api_path = constants.TRANSACTIONS_API_PATH

        self.send(self.config.server_url + api_path, **data)
        self._start_send_timer()

    def _start_send_timer(self, timeout=None):
        timeout = timeout or self.config.flush_interval
        self._send_timer = threading.Timer(timeout, self._collect_transactions)
        self._send_timer.start()

    def _stop_send_timer(self):
        if self._send_timer and not self._send_timer == threading.current_thread():
            self._send_timer.cancel()
            if self._send_timer.is_alive():
                self._send_timer.join()

    def _send_remote(self, url, data, headers=None):
        if headers is None:
            headers = {}
        parsed = compat.urlparse.urlparse(url)
        transport = self._get_transport(parsed)
        if transport.async_mode:
            transport.send_async(
                data, headers, success_callback=self.handle_transport_success, fail_callback=self.handle_transport_fail
            )
        else:
            url = transport.send(data, headers, timeout=self.config.server_timeout)
            self.handle_transport_success(url=url)

    def get_service_info(self):
        if self._service_info:
            return self._service_info
        language_version = platform.python_version()
        if hasattr(sys, "pypy_version_info"):
            runtime_version = ".".join(map(str, sys.pypy_version_info[:3]))
        else:
            runtime_version = language_version
        result = {
            "name": keyword_field(self.config.service_name),
            "environment": keyword_field(self.config.environment),
            "version": keyword_field(self.config.service_version),
            "agent": {"name": "python", "version": elasticapm.VERSION},
            "language": {"name": "python", "version": keyword_field(platform.python_version())},
            "runtime": {
                "name": keyword_field(platform.python_implementation()),
                "version": keyword_field(runtime_version),
            },
        }
        if self.config.framework_name:
            result["framework"] = {
                "name": keyword_field(self.config.framework_name),
                "version": keyword_field(self.config.framework_version),
            }
        self._service_info = result
        return result

    def get_process_info(self):
        return {
            "pid": os.getpid(),
            "ppid": os.getppid() if hasattr(os, "getppid") else None,
            "argv": sys.argv,
            "title": None,  # Note: if we implement this, the value needs to be wrapped with keyword_field
        }

    def get_system_info(self):
        return {
            "hostname": keyword_field(socket.gethostname()),
            "architecture": platform.machine(),
            "platform": platform.system().lower(),
        }

    def _build_msg(self, data=None, **kwargs):
        data = data or {}
        data["service"] = self.get_service_info()
        data["process"] = self.get_process_info()
        data["system"] = self.get_system_info()
        data.update(**kwargs)
        return data

    def _build_msg_for_logging(
        self, event_type, date=None, context=None, custom=None, stack=None, handled=True, **kwargs
    ):
        """
        Captures, processes and serializes an event into a dict object
        """
        transaction = get_transaction()
        if transaction:
            transaction_context = deepcopy(transaction.context)
        else:
            transaction_context = {}
        event_data = {}
        if custom is None:
            custom = {}
        if not date:
            date = datetime.datetime.utcnow()
        if stack is None:
            stack = self.config.auto_log_stacks
        if context:
            transaction_context.update(context)
            context = transaction_context
        else:
            context = transaction_context
        event_data["context"] = context
        if transaction and transaction.tags:
            context["tags"] = deepcopy(transaction.tags)

        # if '.' not in event_type:
        # Assume it's a builtin
        event_type = "elasticapm.events.%s" % event_type

        handler = self.get_handler(event_type)
        result = handler.capture(self, **kwargs)
        if self._filter_exception_type(result):
            return
        # data (explicit) culprit takes over auto event detection
        culprit = result.pop("culprit", None)
        if custom.get("culprit"):
            culprit = custom.pop("culprit")

        for k, v in compat.iteritems(result):
            if k not in event_data:
                event_data[k] = v

        log = event_data.get("log", {})
        if stack and "stacktrace" not in log:
            if stack is True:
                frames = stacks.iter_stack_frames(skip=3)
            else:
                frames = stack
            frames = stacks.get_stack_info(
                frames,
                with_locals=self.config.collect_local_variables in ("errors", "all"),
                library_frame_context_lines=self.config.source_lines_error_library_frames,
                in_app_frame_context_lines=self.config.source_lines_error_app_frames,
                include_paths_re=self.include_paths_re,
                exclude_paths_re=self.exclude_paths_re,
                locals_processor_func=lambda local_var: varmap(
                    lambda k, v: shorten(
                        v,
                        list_length=self.config.local_var_list_max_length,
                        string_length=self.config.local_var_max_length,
                    ),
                    local_var,
                ),
            )
            log["stacktrace"] = frames

        if "stacktrace" in log and not culprit:
            culprit = stacks.get_culprit(log["stacktrace"], self.config.include_paths, self.config.exclude_paths)

        if "level" in log and isinstance(log["level"], compat.integer_types):
            log["level"] = logging.getLevelName(log["level"]).lower()

        if log:
            event_data["log"] = log

        if culprit:
            event_data["culprit"] = culprit

        if "custom" in context:
            context["custom"].update(custom)
        else:
            context["custom"] = custom

        # Run the data through processors
        for processor in self.processors:
            event_data = processor(self, event_data)

        # Make sure all data is coerced
        event_data = transform(event_data)
        if "exception" in event_data:
            event_data["exception"]["handled"] = bool(handled)

        event_data.update({"timestamp": date.strftime(constants.TIMESTAMP_FORMAT)})

        transaction = get_transaction()
        if transaction:
            event_data["transaction"] = {"id": transaction.id}

        return self._build_msg({"errors": [event_data]})

    def _filter_exception_type(self, data):
        exception = data.get("exception")
        if not exception:
            return False

        exc_type = exception.get("type")
        exc_module = exception.get("module")
        if exc_module == "None":
            exc_module = None

        if exc_type in self.filter_exception_types_dict:
            exc_to_filter_module = self.filter_exception_types_dict[exc_type]
            if not exc_to_filter_module or exc_to_filter_module == exc_module:
                if exc_module:
                    exc_name = "%s.%s" % (exc_module, exc_type)
                else:
                    exc_name = exc_type
                self.logger.info("Ignored %s exception due to exception type filter", exc_name)
                return True
        return False

    def _get_log_message(self, data):
        # decode message so we can show the actual event
        try:
            data = self.decode(data)
        except Exception:
            message = "<failed decoding data>"
        else:
            message = data.pop("message", "<no message value>")
        return message

    def _get_transport(self, parsed_url):
        if hasattr(self._transport_class, "sync_transport") and is_master_process():
            # when in the master process, always use SYNC mode. This avoids
            # the danger of being forked into an inconsistent threading state
            self.logger.info("Sending message synchronously while in master " "process. PID: %s", os.getpid())
            return self._transport_class.sync_transport(parsed_url)
        if parsed_url not in self._transports:
            self._transports[parsed_url] = self._transport_class(
                parsed_url, verify_server_cert=self.config.verify_server_cert
            )
        return self._transports[parsed_url]

    def _get_stack_info_for_trace(
        self,
        frames,
        library_frame_context_lines=None,
        in_app_frame_context_lines=None,
        with_locals=True,
        locals_processor_func=None,
    ):
        """Overrideable in derived clients to add frames/info, e.g. templates"""
        return stacks.get_stack_info(
            frames,
            library_frame_context_lines=library_frame_context_lines,
            in_app_frame_context_lines=in_app_frame_context_lines,
            with_locals=with_locals,
            include_paths_re=self.include_paths_re,
            exclude_paths_re=self.exclude_paths_re,
            locals_processor_func=locals_processor_func,
        )


class DummyClient(Client):
    """Sends messages into an empty void"""

    def send(self, url, **kwargs):
        return None
