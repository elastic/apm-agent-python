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


class _ConfigValue(object):
    def __init__(self, dict_key, env_key=None, type=compat.text_type, validators=None, default=None, doc=None):
        self.type = type
        self.dict_key = dict_key
        self.validators = validators
        self.default = default
        self.doc = doc
        if env_key is None:
            env_key = 'ELASTIC_APM_' + dict_key
        self.env_key = env_key

    def __get__(self, instance, owner):
        if instance:
            return instance._values.get(self, self.default)
        else:
            return self.default

    def __set__(self, instance, value):
        if value is not None:
            value = self.type(value)
        instance._values[self] = value


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
        instance._values[self] = value


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
        instance._values[self] = bool(value)


class _ConfigBase(object):
    _NO_VALUE = object()  # sentinel object

    def __init__(self, config_dict=None, env_dict=None, default_dict=None):
        self._values = {}
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
                setattr(self, field, new_value)


class Config(_ConfigBase):
    app_name = _ConfigValue('APP_NAME', validators=[lambda val: re.match('^[a-zA-Z0-9 _-]+$', val)])
    secret_token = _ConfigValue('SECRET_TOKEN')
    servers = _ListConfigValue('SERVERS', default=['http://localhost:8200'])
    include_paths = _ListConfigValue('INCLUDE_PATHS')
    exclude_paths = _ListConfigValue('EXCLUDE_PATHS')
    filter_exception_types = _ListConfigValue('FILTER_EXCEPTION_TYPES')
    timeout = _ConfigValue('TIMEOUT', type=float, default=5)
    hostname = _ConfigValue('HOSTNAME', default=socket.gethostname())
    auto_log_stacks = _BoolConfigValue('AUTO_LOG_STACKS', default=True)
    keyword_max_length = _ConfigValue('KEYWORD_MAX_LENGTH', type=int, default=1024)
    transport_class = _ConfigValue('TRANSPORT_CLASS', default='elasticapm.transport.http_urllib3.AsyncUrllib3Transport')
    processors = _ListConfigValue('PROCESSORS', default=[
        'elasticapm.processors.sanitize_stacktrace_locals',
        'elasticapm.processors.sanitize_http_request_cookies',
        'elasticapm.processors.sanitize_http_headers',
        'elasticapm.processors.sanitize_http_wsgi_env',
        'elasticapm.processors.sanitize_http_request_querystring',
        'elasticapm.processors.sanitize_http_request_body',
    ])
    traces_send_frequency = _ConfigValue('TRACES_SEND_FREQ', type=int, default=60)
    async_mode = _BoolConfigValue('ASYNC_MODE', default=True)
    instrument_django_middleware = _BoolConfigValue('INSTRUMENT_DJANGO_MIDDLEWARE', default=True)
    transactions_ignore_patterns = _ListConfigValue('TRANSACTIONS_IGNORE_PATTERNS', default=[])
    app_version = _ConfigValue('APP_VERSION')
    disable_send = _BoolConfigValue('DISABLE_SEND', default=False)


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
