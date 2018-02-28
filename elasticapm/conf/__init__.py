"""
elasticapm.conf
~~~~~~~~~~

:copyright: (c) 2011-2017 Elasticsearch

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

import logging
import os
import re
import socket

from elasticapm.utils import compat

__all__ = ('setup_logging', 'Config')


class ConfigurationError(ValueError):
    def __init__(self, msg, field_name):
        self.field_name = field_name
        super(ValueError, self).__init__(msg)


class _ConfigValue(object):
    def __init__(self, dict_key, env_key=None, type=compat.text_type, validators=None, default=None, required=False):
        self.type = type
        self.dict_key = dict_key
        self.validators = validators
        self.default = default
        self.required = required
        if env_key is None:
            env_key = 'ELASTIC_APM_' + dict_key
        self.env_key = env_key

    def __get__(self, instance, owner):
        if instance:
            return instance._values.get(self.dict_key, self.default)
        else:
            return self.default

    def __set__(self, instance, value):
        if value is not None:
            value = self.type(value)
        if self._validate(instance, value):
            instance._values[self.dict_key] = value

    def _validate(self, instance, value):
        if value is None and self.required:
            raise ConfigurationError(
                'Configuration error: value for {} is required.'.format(self.dict_key),
                self.dict_key,
            )
        if self.validators and value is not None:
            if not all(validator(value) for validator in self.validators):
                raise ConfigurationError(
                    'Configuration error: value {} is not valid for {}.'.format(value, self.dict_key),
                    self.dict_key,
                )
        instance._errors.pop(self.dict_key, None)
        return True


class _ListConfigValue(_ConfigValue):
    def __init__(self, dict_key, list_separator=',', **kwargs):
        self.list_separator = list_separator
        super(_ListConfigValue, self).__init__(dict_key, **kwargs)

    def __set__(self, instance, value):
        if isinstance(value, compat.string_types):
            value = value.split(self.list_separator)
        elif value is not None:
            value = list(value)
        if value:
            value = [self.type(item) for item in value]
        instance._values[self.dict_key] = value


class _BoolConfigValue(_ConfigValue):
    def __init__(self, dict_key, true_string='true', false_string='false', **kwargs):
        self.true_string = true_string
        self.false_string = false_string
        super(_BoolConfigValue, self).__init__(dict_key, **kwargs)

    def __set__(self, instance, value):
        if isinstance(value, compat.string_types):
            if value.lower() == self.true_string:
                value = True
            elif value.lower() == self.false_string:
                value = False
        instance._values[self.dict_key] = bool(value)


class _ConfigBase(object):
    _NO_VALUE = object()  # sentinel object

    def __init__(self, config_dict=None, env_dict=None, default_dict=None):
        self._values = {}
        self._errors = {}
        if config_dict is None:
            config_dict = {}
        if env_dict is None:
            env_dict = os.environ
        if default_dict is None:
            default_dict = {}
        for field, config_value in self.__class__.__dict__.items():
            if not isinstance(config_value, _ConfigValue):
                continue
            new_value = self._NO_VALUE
            # check config dictionary first
            if config_value.dict_key in config_dict:
                new_value = config_dict[config_value.dict_key]
            # then check environment
            elif config_value.env_key and config_value.env_key in env_dict:
                new_value = env_dict[config_value.env_key]
            # finally, if no value is set, check the client-provided defaults
            elif field in default_dict:
                new_value = default_dict[field]
            # only set if new_value changed. We'll fall back to the field default if not.
            if new_value is not self._NO_VALUE:
                try:
                    setattr(self, field, new_value)
                except ConfigurationError as e:
                    self._errors[e.field_name] = str(e)

    @property
    def errors(self):
        return self._errors


class Config(_ConfigBase):
    service_name = _ConfigValue('SERVICE_NAME', validators=[lambda val: re.match('^[a-zA-Z0-9 _-]+$', val)],
                                required=True)
    environment = _ConfigValue('ENVIRONMENT', default=None)
    secret_token = _ConfigValue('SECRET_TOKEN')
    debug = _BoolConfigValue('DEBUG', default=False)
    server_url = _ConfigValue('SERVER_URL', default='http://localhost:8200', required=True)
    verify_server_cert = _BoolConfigValue('VERIFY_SERVER_CERT', default=True)
    include_paths = _ListConfigValue('INCLUDE_PATHS')
    exclude_paths = _ListConfigValue('EXCLUDE_PATHS', default=compat.get_default_library_patters())
    filter_exception_types = _ListConfigValue('FILTER_EXCEPTION_TYPES')
    server_timeout = _ConfigValue('SERVER_TIMEOUT', type=float, default=5)
    hostname = _ConfigValue('HOSTNAME', default=socket.gethostname())
    auto_log_stacks = _BoolConfigValue('AUTO_LOG_STACKS', default=True)
    transport_class = _ConfigValue('TRANSPORT_CLASS', default='elasticapm.transport.http.AsyncTransport',
                                   required=True)
    processors = _ListConfigValue('PROCESSORS', default=[
        'elasticapm.processors.sanitize_stacktrace_locals',
        'elasticapm.processors.sanitize_http_request_cookies',
        'elasticapm.processors.sanitize_http_headers',
        'elasticapm.processors.sanitize_http_wsgi_env',
        'elasticapm.processors.sanitize_http_request_querystring',
        'elasticapm.processors.sanitize_http_request_body',
    ])
    flush_interval = _ConfigValue('FLUSH_INTERVAL', type=int, default=10)
    transaction_sample_rate = _ConfigValue('TRANSACTION_SAMPLE_RATE', type=float, default=1.0)
    transaction_max_spans = _ConfigValue('TRANSACTION_MAX_SPANS', type=int, default=500)
    span_frames_min_duration_ms = _ConfigValue('SPAN_FRAMES_MIN_DURATION', default=-1, type=int)
    max_queue_size = _ConfigValue('MAX_QUEUE_SIZE', type=int, default=500)
    collect_local_variables = _ConfigValue('COLLECT_LOCAL_VARIABLES', default='errors')
    source_lines_error_app_frames = _ConfigValue('SOURCE_LINES_ERROR_APP_FRAMES', type=int, default=5)
    source_lines_error_library_frames = _ConfigValue('SOURCE_LINES_ERROR_LIBRARY_FRAMES', type=int, default=5)
    source_lines_span_app_frames = _ConfigValue('SOURCE_LINES_SPAN_APP_FRAMES', type=int, default=0)
    source_lines_span_library_frames = _ConfigValue('SOURCE_LINES_SPAN_LIBRARY_FRAMES', type=int, default=0)
    local_var_max_length = _ConfigValue('LOCAL_VAR_MAX_LENGTH', type=int, default=200)
    local_var_list_max_length = _ConfigValue('LOCAL_VAR_LIST_MAX_LENGTH', type=int, default=10)
    capture_body = _ConfigValue('CAPTURE_BODY', default='off')
    async_mode = _BoolConfigValue('ASYNC_MODE', default=True)
    instrument_django_middleware = _BoolConfigValue('INSTRUMENT_DJANGO_MIDDLEWARE', default=True)
    transactions_ignore_patterns = _ListConfigValue('TRANSACTIONS_IGNORE_PATTERNS', default=[])
    service_version = _ConfigValue('SERVICE_VERSION')
    framework_name = _ConfigValue('FRAMEWORK_NAME', default=None)
    framework_version = _ConfigValue('FRAMEWORK_VERSION', default=None)
    disable_send = _BoolConfigValue('DISABLE_SEND', default=False)
    instrument = _BoolConfigValue('DISABLE_INSTRUMENTATION', default=True)

    # undocumented configuration
    _wait_to_first_send = _ConfigValue('_WAIT_TO_FIRST_SEND', type=int, default=5)


def setup_logging(handler, exclude=['elasticapm',
                                    'gunicorn',
                                    'south',
                                    'elasticapm.errors']):
    """
    Configures logging to pipe to Elastic APM.

    - ``exclude`` is a list of loggers that shouldn't go to ElasticAPM.

    For a typical Python install:

    >>> from elasticapm.handlers.logging import LoggingHandler
    >>> client = ElasticAPM(...)
    >>> setup_logging(LoggingHandler(client))

    Within Django:

    >>> from elasticapm.contrib.django.handlers import LoggingHandler
    >>> setup_logging(LoggingHandler())

    Returns a boolean based on if logging was configured or not.
    """
    logger = logging.getLogger()
    if handler.__class__ in map(type, logger.handlers):
        return False

    logger.addHandler(handler)

    # Add StreamHandler to sentry's default so you can catch missed exceptions
    for logger_name in exclude:
        logger = logging.getLogger(logger_name)
        logger.propagate = False
        logger.addHandler(logging.StreamHandler())

    return True
