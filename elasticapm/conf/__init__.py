#  BSD 3-Clause License
#
#  Copyright (c) 2012, the Sentry Team, see AUTHORS for more details
#  Copyright (c) 2019, Elasticsearch BV
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  * Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE


import logging
import logging.handlers
import math
import os
import re
import threading
from datetime import timedelta

import _hashlib

from elasticapm.conf.constants import BASE_SANITIZE_FIELD_NAMES, TRACE_CONTINUATION_STRATEGY
from elasticapm.utils import compat, starmatch_to_regex
from elasticapm.utils.logging import get_logger
from elasticapm.utils.threading import IntervalTimer, ThreadManager

__all__ = ("setup_logging", "Config")


logger = get_logger("elasticapm.conf")

log_levels_map = {
    "trace": 5,
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "warn": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
    "off": 1000,
}
logfile_set_up = False


class ConfigurationError(ValueError):
    def __init__(self, msg, field_name) -> None:
        self.field_name = field_name
        super(ValueError, self).__init__(msg)


class _ConfigValue(object):
    """
    Base class for configuration values

    dict_key
        String representing the key used for this config value in dict configs.
    env_key
        String representing the key used in environment variables for this
        config value. If not specified, will be set to `"ELASTIC_APM_" + dict_key`.
    type
        Type of value stored in this config value.
    validators
        List of validator classes. Must be callables, which will be called with
        a value and the dict_key for the config value. The validator either
        returns the validated value or raises a ConfigurationError if validation
        fails.
    callbacks
        List of functions which will be called when the config value is updated.
        The callbacks must match this signature:
            callback(dict_key, old_value, new_value, config_instance)

        Note that callbacks wait until the end of any given `update()` operation
        and are called at this point. This, coupled with the fact that callbacks
        receive the config instance, means that callbacks can utilize multiple
        configuration values (such as is the case for logging). This is
        complicated if more than one of the involved config values are
        dynamic, as both would need callbacks and the callback would need to
        be idempotent.
    callbacks_on_default
        Whether the callback should be called on config initialization if the
        default value is used. Default: True
    default
        The default for this config value if not user-configured.
    required
        Whether this config value is required. If a default is specified,
        this is a redundant option (except to ensure that this config value
        is specified if a default were ever to be removed).

    Note that _ConfigValues and any inheriting classes must implement __set__
    and __get__. The calling instance will always be a _ConfigBase descendant
    and the __set__ and __get__ calls will access `instance._values[self.dict_key]`
    to get and set values.
    """

    def __init__(
        self,
        dict_key,
        env_key=None,
        type=str,
        validators=None,
        callbacks=None,
        callbacks_on_default=True,
        default=None,
        required=False,
    ) -> None:
        self.type = type
        self.dict_key = dict_key
        self.validators = validators
        self.callbacks = callbacks
        self.default = default
        self.required = required
        if env_key is None:
            env_key = "ELASTIC_APM_" + dict_key
        self.env_key = env_key
        self.callbacks_on_default = callbacks_on_default

    def __get__(self, instance, owner):
        if instance:
            return instance._values.get(self.dict_key, self.default)
        else:
            return self.default

    def __set__(self, config_instance, value) -> None:
        value = self._validate(config_instance, value)
        self._callback_if_changed(config_instance, value)
        config_instance._values[self.dict_key] = value

    def _validate(self, instance, value):
        if value is None and self.required:
            raise ConfigurationError(
                "Configuration error: value for {} is required.".format(self.dict_key), self.dict_key
            )
        if self.validators and value is not None:
            for validator in self.validators:
                value = validator(value, self.dict_key)
        if self.type and value is not None:
            try:
                value = self.type(value)
            except ValueError as e:
                raise ConfigurationError("{}: {}".format(self.dict_key, str(e)), self.dict_key)
        instance._errors.pop(self.dict_key, None)
        return value

    def _callback_if_changed(self, instance, new_value) -> None:
        """
        If the value changed (checked against instance._values[self.dict_key]),
        then run the callback function (if defined)
        """
        old_value = instance._values.get(self.dict_key, self.default)
        if old_value != new_value:
            instance.callbacks_queue.append((self.dict_key, old_value, new_value))

    def call_callbacks(self, old_value, new_value, config_instance):
        if not self.callbacks:
            return
        for callback in self.callbacks:
            try:
                callback(self.dict_key, old_value, new_value, config_instance)
            except Exception as e:
                raise ConfigurationError(
                    "Callback {} raised an exception when setting {} to {}: {}".format(
                        callback, self.dict_key, new_value, e
                    ),
                    self.dict_key,
                )


class _ListConfigValue(_ConfigValue):
    def __init__(self, dict_key, list_separator=",", **kwargs) -> None:
        self.list_separator = list_separator
        super(_ListConfigValue, self).__init__(dict_key, **kwargs)

    def __set__(self, instance, value) -> None:
        if isinstance(value, str):
            value = value.split(self.list_separator)
        elif value is not None:
            value = list(value)
        if value:
            value = [self.type(item) for item in value]
        self._callback_if_changed(instance, value)
        instance._values[self.dict_key] = value


class _DictConfigValue(_ConfigValue):
    def __init__(self, dict_key, item_separator=",", keyval_separator="=", **kwargs) -> None:
        self.item_separator = item_separator
        self.keyval_separator = keyval_separator
        super(_DictConfigValue, self).__init__(dict_key, **kwargs)

    def __set__(self, instance, value) -> None:
        if isinstance(value, str):
            items = (item.split(self.keyval_separator) for item in value.split(self.item_separator))
            value = {key.strip(): self.type(val.strip()) for key, val in items}
        elif not isinstance(value, dict):
            # TODO: better error handling
            value = None
        self._callback_if_changed(instance, value)
        instance._values[self.dict_key] = value


class _BoolConfigValue(_ConfigValue):
    def __init__(self, dict_key, true_string="true", false_string="false", **kwargs) -> None:
        self.true_string = true_string
        self.false_string = false_string
        # this is necessary to have the bool type preserved in _validate
        kwargs["type"] = bool
        super(_BoolConfigValue, self).__init__(dict_key, **kwargs)

    def __set__(self, instance, value) -> None:
        if isinstance(value, str):
            if value.lower() == self.true_string:
                value = True
            elif value.lower() == self.false_string:
                value = False
        value = self._validate(instance, value)
        self._callback_if_changed(instance, value)
        instance._values[self.dict_key] = bool(value)


class _DurationConfigValue(_ConfigValue):
    units = (
        ("us", 0.000001),
        ("ms", 0.001),
        ("s", 1),
        ("m", 60),
    )

    def __init__(self, dict_key, allow_microseconds=False, unitless_factor=None, **kwargs) -> None:
        self.type = None  # no type coercion
        used_units = self.units if allow_microseconds else self.units[1:]
        pattern = "|".join(unit[0] for unit in used_units)
        unit_multipliers = dict(used_units)
        unit_required = ""
        if unitless_factor:
            unit_multipliers[None] = unitless_factor
            unit_required = "?"
        regex = f"((?:-)?\\d+)({pattern}){unit_required}$"
        verbose_pattern = f"\\d+({pattern}){unit_required}$"
        duration_validator = UnitValidator(
            regex=regex, verbose_pattern=verbose_pattern, unit_multipliers=unit_multipliers
        )
        validators = kwargs.pop("validators", [])
        validators.insert(0, duration_validator)
        super().__init__(dict_key, validators=validators, **kwargs)

    def __set__(self, config_instance, value) -> None:
        value = self._validate(config_instance, value)
        value = timedelta(seconds=float(value))
        self._callback_if_changed(config_instance, value)
        config_instance._values[self.dict_key] = value


class RegexValidator(object):
    def __init__(self, regex, verbose_pattern=None) -> None:
        self.regex = regex
        self.verbose_pattern = verbose_pattern or regex

    def __call__(self, value, field_name):
        value = str(value)
        match = re.match(self.regex, value)
        if match:
            return value
        raise ConfigurationError(
            "{}={} does not match pattern {}".format(
                field_name,
                value,
                self.verbose_pattern,
            ),
            field_name,
        )


class UnitValidator(object):
    def __init__(self, regex, verbose_pattern, unit_multipliers) -> None:
        self.regex = regex
        self.verbose_pattern = verbose_pattern
        self.unit_multipliers = unit_multipliers

    def __call__(self, value, field_name):
        value = str(value)
        match = re.match(self.regex, value, re.IGNORECASE)
        if not match:
            raise ConfigurationError(
                "{}={} does not match pattern {}".format(
                    field_name,
                    value,
                    self.verbose_pattern,
                ),
                field_name,
            )
        val, unit = match.groups()
        try:
            val = int(val) * self.unit_multipliers[unit]
        except KeyError:
            raise ConfigurationError("{}={} is not a supported unit".format(field_name, unit), field_name)
        return val


class PrecisionValidator(object):
    """
    Forces a float value to `precision` digits of precision.

    Rounds half away from zero.

    If `minimum` is provided, and the value rounds to 0 (but was not zero to
    begin with), use the minimum instead.
    """

    def __init__(self, precision=0, minimum=None) -> None:
        self.precision = precision
        self.minimum = minimum

    def __call__(self, value, field_name):
        try:
            value = float(value)
        except ValueError:
            raise ConfigurationError("{}={} is not a float".format(field_name, value), field_name)
        multiplier = 10**self.precision
        rounded = math.floor(value * multiplier + 0.5) / multiplier
        if rounded == 0 and self.minimum and value != 0:
            rounded = self.minimum
        return rounded


size_validator = UnitValidator(
    r"^(\d+)(b|kb|mb|gb)$", r"\d+(b|KB|MB|GB)", {"b": 1, "kb": 1024, "mb": 1024 * 1024, "gb": 1024 * 1024 * 1024}
)


class ExcludeRangeValidator(object):
    def __init__(self, range_start, range_end, range_desc) -> None:
        self.range_start = range_start
        self.range_end = range_end
        self.range_desc = range_desc

    def __call__(self, value, field_name):
        if self.range_start <= value <= self.range_end:
            raise ConfigurationError(
                "{}={} cannot be in range: {}".format(
                    field_name,
                    value,
                    self.range_desc.format(**{"range_start": self.range_start, "range_end": self.range_end}),
                ),
                field_name,
            )
        return value


class FileIsReadableValidator(object):
    def __call__(self, value, field_name):
        value = os.path.normpath(value)
        if not os.path.exists(value):
            raise ConfigurationError("{}={} does not exist".format(field_name, value), field_name)
        elif not os.path.isfile(value):
            raise ConfigurationError("{}={} is not a file".format(field_name, value), field_name)
        elif not os.access(value, os.R_OK):
            raise ConfigurationError("{}={} is not readable".format(field_name, value), field_name)
        return value


def _in_fips_mode():
    try:
        return _hashlib.get_fips_mode() == 1
    except AttributeError:
        # versions older of Python3.9 do not have the helper
        return False


class SupportedValueInFipsModeValidator(object):
    """If FIPS mode is enabled only supported_value is accepted"""

    def __init__(self, supported_value) -> None:
        self.supported_value = supported_value

    def __call__(self, value, field_name):
        if _in_fips_mode():
            if value != self.supported_value:
                raise ConfigurationError(
                    "{}={} must be set to {} if FIPS mode is enabled".format(field_name, value, self.supported_value),
                    field_name,
                )
        return value


class EnumerationValidator(object):
    """
    Validator which ensures that a given config value is chosen from a list
    of valid string options.
    """

    def __init__(self, valid_values, case_sensitive=False) -> None:
        """
        valid_values
            List of valid string values for the config value
        case_sensitive
            Whether to compare case when comparing a value to the valid list.
            Defaults to False (case-insensitive)
        """
        self.case_sensitive = case_sensitive
        if case_sensitive:
            self.valid_values = {s: s for s in valid_values}
        else:
            self.valid_values = {s.lower(): s for s in valid_values}

    def __call__(self, value, field_name):
        if self.case_sensitive:
            ret = self.valid_values.get(value)
        else:
            ret = self.valid_values.get(value.lower())
        if ret is None:
            raise ConfigurationError(
                "{}={} is not in the list of valid values: {}".format(
                    field_name,
                    value,
                    list(self.valid_values.values()),
                ),
                field_name,
            )
        return ret


def _log_level_callback(dict_key, old_value, new_value, config_instance) -> None:
    elasticapm_logger = logging.getLogger("elasticapm")
    elasticapm_logger.setLevel(log_levels_map.get(new_value, 100))

    global logfile_set_up
    if not logfile_set_up and config_instance.log_file:
        logfile_set_up = True
        filehandler = logging.handlers.RotatingFileHandler(
            config_instance.log_file, maxBytes=config_instance.log_file_size, backupCount=1
        )
        try:
            import ecs_logging

            filehandler.setFormatter(ecs_logging.StdlibFormatter())
        except ImportError:
            pass
        elasticapm_logger.addHandler(filehandler)


def _log_ecs_reformatting_callback(dict_key, old_value, new_value, config_instance) -> None:
    """
    If ecs_logging is installed and log_ecs_reformatting is set to "override", we should
    set the ecs_logging.StdlibFormatter as the formatted for every handler in
    the root logger, and set the default processor for structlog to the
    ecs_logging.StructlogFormatter.
    """
    if new_value.lower() == "override":
        try:
            import ecs_logging
        except ImportError:
            return

        # Stdlib
        root_logger = logging.getLogger()
        formatter = ecs_logging.StdlibFormatter()
        for handler in root_logger.handlers:
            handler.setFormatter(formatter)

        # Structlog
        try:
            import structlog

            structlog.configure(processors=[ecs_logging.StructlogFormatter()])
        except ImportError:
            pass


class _ConfigBase(object):
    _NO_VALUE = object()  # sentinel object

    def __init__(self, config_dict=None, env_dict=None, inline_dict=None, copy=False) -> None:
        """
        config_dict
            Configuration dict as is common for frameworks such as flask and django.
            Keys match the _ConfigValue.dict_key (usually all caps)
        env_dict
            Environment variables dict. Keys match the _ConfigValue.env_key
            (usually "ELASTIC_APM_" + dict_key)
        inline_dict
            Any config passed in as kwargs to the Client object. Typically
            the keys match the names of the _ConfigValue variables in the Config
            object.
        copy
            Whether this object is being created to copy an existing Config
            object. If True, don't run the initial `update` (which would call
            callbacks if present)
        """
        self._values = {}
        self._errors = {}
        self._dict_key_lookup = {}
        self.callbacks_queue = []
        for config_value in self.__class__.__dict__.values():
            if not isinstance(config_value, _ConfigValue):
                continue
            self._dict_key_lookup[config_value.dict_key] = config_value
        if not copy:
            self.update(config_dict, env_dict, inline_dict, initial=True)

    def update(self, config_dict=None, env_dict=None, inline_dict=None, initial=False) -> None:
        if config_dict is None:
            config_dict = {}
        if env_dict is None:
            env_dict = os.environ
        if inline_dict is None:
            inline_dict = {}
        for field, config_value in self.__class__.__dict__.items():
            if not isinstance(config_value, _ConfigValue):
                continue
            new_value = self._NO_VALUE
            # first check environment
            if config_value.env_key and config_value.env_key in env_dict:
                new_value = env_dict[config_value.env_key]
            # check the inline config
            elif field in inline_dict:
                new_value = inline_dict[field]
            # finally, check config dictionary
            elif config_value.dict_key in config_dict:
                new_value = config_dict[config_value.dict_key]
            # only set if new_value changed. We'll fall back to the field default if not.
            if new_value is not self._NO_VALUE:
                try:
                    setattr(self, field, new_value)
                except ConfigurationError as e:
                    self._errors[e.field_name] = str(e)
            # handle initial callbacks
            if (
                initial
                and config_value.callbacks_on_default
                and getattr(self, field) is not None
                and getattr(self, field) == config_value.default
            ):
                self.callbacks_queue.append((config_value.dict_key, self._NO_VALUE, config_value.default))
            # if a field has not been provided by any config source, we have to check separately if it is required
            if config_value.required and getattr(self, field) is None:
                self._errors[config_value.dict_key] = "Configuration error: value for {} is required.".format(
                    config_value.dict_key
                )
        self.call_pending_callbacks()

    def call_pending_callbacks(self) -> None:
        """
        Call callbacks for config options matching list of tuples:

        (dict_key, old_value, new_value)
        """
        for dict_key, old_value, new_value in self.callbacks_queue:
            self._dict_key_lookup[dict_key].call_callbacks(old_value, new_value, self)
        self.callbacks_queue = []

    @property
    def values(self):
        return self._values

    @values.setter
    def values(self, values) -> None:
        self._values = values

    @property
    def errors(self):
        return self._errors

    def copy(self):
        c = self.__class__(copy=True)
        c._errors = {}
        c.values = self.values.copy()
        return c


class WrapperConfig(_ConfigBase):
    enabled = _BoolConfigValue("ENABLED", default=True)
    instrument = _BoolConfigValue("INSTRUMENT", default=True)


class Config(_ConfigBase):
    service_name = _ConfigValue(
        "SERVICE_NAME",
        validators=[RegexValidator("^[a-zA-Z0-9 _-]+$")],
        default="unknown-python-service",
        required=True,
    )
    service_node_name = _ConfigValue("SERVICE_NODE_NAME")
    environment = _ConfigValue("ENVIRONMENT")
    transport_json_serializer = _ConfigValue("TRANSPORT_JSON_SERIALIZER")
    secret_token = _ConfigValue("SECRET_TOKEN")
    api_key = _ConfigValue("API_KEY")
    debug = _BoolConfigValue("DEBUG", default=False)
    server_url = _ConfigValue("SERVER_URL", default="http://127.0.0.1:8200", required=True)
    server_cert = _ConfigValue("SERVER_CERT", validators=[FileIsReadableValidator()])
    server_ca_cert_file = _ConfigValue("SERVER_CA_CERT_FILE", validators=[FileIsReadableValidator()])
    verify_server_cert = _BoolConfigValue(
        "VERIFY_SERVER_CERT", default=True, validators=[SupportedValueInFipsModeValidator(supported_value=True)]
    )
    use_certifi = _BoolConfigValue("USE_CERTIFI", default=True)
    include_paths = _ListConfigValue("INCLUDE_PATHS")
    exclude_paths = _ListConfigValue("EXCLUDE_PATHS", default=compat.get_default_library_patters())
    filter_exception_types = _ListConfigValue("FILTER_EXCEPTION_TYPES")
    server_timeout = _ConfigValue(
        "SERVER_TIMEOUT",
        type=float,
        validators=[
            UnitValidator(r"^((?:-)?\d+)(ms|s|m)?$", r"\d+(ms|s|m)", {"ms": 0.001, "s": 1, "m": 60, None: 1000})
        ],
        default=5,
    )
    hostname = _ConfigValue("HOSTNAME", default=None)
    auto_log_stacks = _BoolConfigValue("AUTO_LOG_STACKS", default=True)
    transport_class = _ConfigValue("TRANSPORT_CLASS", default="elasticapm.transport.http.Transport", required=True)
    processors = _ListConfigValue(
        "PROCESSORS",
        default=[
            "elasticapm.processors.sanitize_stacktrace_locals",
            "elasticapm.processors.sanitize_http_request_cookies",
            "elasticapm.processors.sanitize_http_response_cookies",
            "elasticapm.processors.sanitize_http_headers",
            "elasticapm.processors.sanitize_http_wsgi_env",
            "elasticapm.processors.sanitize_http_request_body",
        ],
    )
    sanitize_field_names = _ListConfigValue(
        "SANITIZE_FIELD_NAMES", type=starmatch_to_regex, default=BASE_SANITIZE_FIELD_NAMES
    )
    metrics_sets = _ListConfigValue(
        "METRICS_SETS",
        default=[
            "elasticapm.metrics.sets.cpu.CPUMetricSet",
        ],
    )
    metrics_interval = _DurationConfigValue(
        "METRICS_INTERVAL",
        validators=[ExcludeRangeValidator(0.001, 0.999, "{range_start} - {range_end} s")],
        default=timedelta(seconds=30),
    )
    breakdown_metrics = _BoolConfigValue("BREAKDOWN_METRICS", default=True)
    prometheus_metrics = _BoolConfigValue("PROMETHEUS_METRICS", default=False)
    prometheus_metrics_prefix = _ConfigValue("PROMETHEUS_METRICS_PREFIX", default="prometheus.metrics.")
    disable_metrics = _ListConfigValue("DISABLE_METRICS", type=starmatch_to_regex, default=[])
    central_config = _BoolConfigValue("CENTRAL_CONFIG", default=True)
    api_request_size = _ConfigValue("API_REQUEST_SIZE", type=int, validators=[size_validator], default=768 * 1024)
    api_request_time = _DurationConfigValue("API_REQUEST_TIME", default=timedelta(seconds=10))
    transaction_sample_rate = _ConfigValue(
        "TRANSACTION_SAMPLE_RATE", type=float, validators=[PrecisionValidator(4, 0.0001)], default=1.0
    )
    transaction_max_spans = _ConfigValue("TRANSACTION_MAX_SPANS", type=int, default=500)
    stack_trace_limit = _ConfigValue("STACK_TRACE_LIMIT", type=int, default=50)
    span_frames_min_duration = _DurationConfigValue(
        "SPAN_FRAMES_MIN_DURATION", default=timedelta(seconds=0.005), unitless_factor=0.001
    )
    span_stack_trace_min_duration = _DurationConfigValue(
        "SPAN_STACK_TRACE_MIN_DURATION", default=timedelta(seconds=0.005), unitless_factor=0.001
    )
    span_compression_enabled = _BoolConfigValue("SPAN_COMPRESSION_ENABLED", default=True)
    span_compression_exact_match_max_duration = _DurationConfigValue(
        "SPAN_COMPRESSION_EXACT_MATCH_MAX_DURATION",
        default=timedelta(seconds=0.05),
    )
    span_compression_same_kind_max_duration = _DurationConfigValue(
        "SPAN_COMPRESSION_SAME_KIND_MAX_DURATION",
        default=timedelta(seconds=0),
    )
    exit_span_min_duration = _DurationConfigValue(
        "EXIT_SPAN_MIN_DURATION",
        default=timedelta(seconds=0),
    )
    collect_local_variables = _ConfigValue("COLLECT_LOCAL_VARIABLES", default="errors")
    source_lines_error_app_frames = _ConfigValue("SOURCE_LINES_ERROR_APP_FRAMES", type=int, default=5)
    source_lines_error_library_frames = _ConfigValue("SOURCE_LINES_ERROR_LIBRARY_FRAMES", type=int, default=5)
    source_lines_span_app_frames = _ConfigValue("SOURCE_LINES_SPAN_APP_FRAMES", type=int, default=0)
    source_lines_span_library_frames = _ConfigValue("SOURCE_LINES_SPAN_LIBRARY_FRAMES", type=int, default=0)
    local_var_max_length = _ConfigValue("LOCAL_VAR_MAX_LENGTH", type=int, default=200)
    local_var_list_max_length = _ConfigValue("LOCAL_VAR_LIST_MAX_LENGTH", type=int, default=10)
    local_var_dict_max_length = _ConfigValue("LOCAL_VAR_DICT_MAX_LENGTH", type=int, default=10)
    capture_body = _ConfigValue(
        "CAPTURE_BODY",
        default="off",
        validators=[lambda val, _: {"errors": "error", "transactions": "transaction"}.get(val, val)],
    )
    async_mode = _BoolConfigValue("ASYNC_MODE", default=True)
    instrument_django_middleware = _BoolConfigValue("INSTRUMENT_DJANGO_MIDDLEWARE", default=True)
    autoinsert_django_middleware = _BoolConfigValue("AUTOINSERT_DJANGO_MIDDLEWARE", default=True)
    transactions_ignore_patterns = _ListConfigValue("TRANSACTIONS_IGNORE_PATTERNS", default=[])
    transaction_ignore_urls = _ListConfigValue("TRANSACTION_IGNORE_URLS", type=starmatch_to_regex, default=[])
    ignore_message_queues = _ListConfigValue("IGNORE_MESSAGE_QUEUES", type=starmatch_to_regex, default=[])
    service_version = _ConfigValue("SERVICE_VERSION")
    framework_name = _ConfigValue("FRAMEWORK_NAME")
    framework_version = _ConfigValue("FRAMEWORK_VERSION")
    global_labels = _DictConfigValue("GLOBAL_LABELS")
    disable_send = _BoolConfigValue("DISABLE_SEND", default=False)
    enabled = _BoolConfigValue("ENABLED", default=True)
    recording = _BoolConfigValue("RECORDING", default=True)
    instrument = _BoolConfigValue("INSTRUMENT", default=True)
    enable_distributed_tracing = _BoolConfigValue("ENABLE_DISTRIBUTED_TRACING", default=True)
    capture_headers = _BoolConfigValue("CAPTURE_HEADERS", default=True)
    django_transaction_name_from_route = _BoolConfigValue("DJANGO_TRANSACTION_NAME_FROM_ROUTE", default=False)
    disable_log_record_factory = _BoolConfigValue("DISABLE_LOG_RECORD_FACTORY", default=False)
    use_elastic_traceparent_header = _BoolConfigValue("USE_ELASTIC_TRACEPARENT_HEADER", default=True)
    use_elastic_excepthook = _BoolConfigValue("USE_ELASTIC_EXCEPTHOOK", default=False)
    cloud_provider = _ConfigValue("CLOUD_PROVIDER", default=True)
    log_level = _ConfigValue(
        "LOG_LEVEL",
        validators=[EnumerationValidator(["trace", "debug", "info", "warning", "warn", "error", "critical", "off"])],
        callbacks=[_log_level_callback],
    )
    log_file = _ConfigValue("LOG_FILE", default="")
    log_file_size = _ConfigValue("LOG_FILE_SIZE", validators=[size_validator], type=int, default=50 * 1024 * 1024)
    log_ecs_reformatting = _ConfigValue(
        "LOG_ECS_REFORMATTING",
        validators=[EnumerationValidator(["off", "override"])],
        callbacks=[_log_ecs_reformatting_callback],
        default="off",
    )
    trace_continuation_strategy = _ConfigValue(
        "TRACE_CONTINUATION_STRATEGY",
        validators=[
            EnumerationValidator(
                [
                    TRACE_CONTINUATION_STRATEGY.CONTINUE,
                    TRACE_CONTINUATION_STRATEGY.RESTART,
                    TRACE_CONTINUATION_STRATEGY.RESTART_EXTERNAL,
                ]
            )
        ],
        default=TRACE_CONTINUATION_STRATEGY.CONTINUE,
    )
    include_process_args = _BoolConfigValue("INCLUDE_PROCESS_ARGS", default=False)

    @property
    def is_recording(self):
        if not self.enabled:
            return False
        else:
            return self.recording


class VersionedConfig(ThreadManager):
    """
    A thin layer around Config that provides versioning
    """

    __slots__ = (
        "_config",
        "_version",
        "_first_config",
        "_first_version",
        "_lock",
        "transport",
        "_update_thread",
        "pid",
        "start_stop_order",
    )

    def __init__(self, config_object, version, transport=None) -> None:
        """
        Create a new VersionedConfig with an initial Config object
        :param config_object: the initial Config object
        :param version: a version identifier for the configuration
        """
        self._config = self._first_config = config_object
        self._version = self._first_version = version
        self.transport = transport
        self._lock = threading.Lock()
        self._update_thread = None
        super(VersionedConfig, self).__init__()

    def update(self, version: str, **config):
        """
        Update the configuration version
        :param version: version identifier for the new configuration
        :param config: a key/value map of new configuration
        :return: configuration errors, if any
        """
        new_config = self._config.copy()

        # pass an empty env dict to ensure the environment doesn't get precedence
        new_config.update(inline_dict=config, env_dict={})
        if not new_config.errors:
            with self._lock:
                self._version = version
                self._config = new_config
        else:
            return new_config.errors

    def reset(self) -> None:
        """
        Reset state to the original configuration

        Note that because ConfigurationValues can have callbacks, we need to
        note any differences between the original configuration and the most
        recent configuration and run any callbacks that might exist for those
        values.
        """
        callbacks = []
        for key in self._config.values.keys():
            if key in self._first_config.values and self._config.values[key] != self._first_config.values[key]:
                callbacks.append((key, self._config.values[key], self._first_config.values[key]))

        with self._lock:
            self._version = self._first_version
            self._config = self._first_config

        self._config.callbacks_queue.extend(callbacks)
        self._config.call_pending_callbacks()

    @property
    def changed(self) -> bool:
        return self._config != self._first_config

    def __getattr__(self, item):
        return getattr(self._config, item)

    def __setattr__(self, name, value) -> None:
        if name not in self.__slots__:
            setattr(self._config, name, value)
        else:
            super(VersionedConfig, self).__setattr__(name, value)

    @property
    def config_version(self):
        return self._version

    def update_config(self):
        if not self.transport:
            logger.warning("No transport set for config updates, skipping")
            return
        logger.debug("Checking for new config...")
        keys = {"service": {"name": self.service_name}}
        if self.environment:
            keys["service"]["environment"] = self.environment
        new_version, new_config, next_run = self.transport.get_config(self.config_version, keys)
        if new_version and new_config:
            errors = self.update(new_version, **new_config)
            if errors:
                logger.error("Error applying new configuration: %s", repr(errors))
            else:
                logger.info(
                    "Applied new remote configuration: %s",
                    "; ".join("%s=%s" % (str(k), str(v)) for k, v in new_config.items()),
                )
        elif new_version == self.config_version:
            logger.debug("Remote config unchanged")
        elif not new_config and self.changed:
            logger.debug("Remote config disappeared, resetting to original")
            self.reset()

        return next_run

    def start_thread(self, pid=None) -> None:
        self._update_thread = IntervalTimer(
            self.update_config, 1, "eapm conf updater", daemon=True, evaluate_function_interval=True
        )
        self._update_thread.start()
        super(VersionedConfig, self).start_thread(pid=pid)

    def stop_thread(self) -> None:
        if self._update_thread:
            self._update_thread.cancel()
            self._update_thread = None


def setup_logging(handler):
    """
    Configures logging to pipe to Elastic APM.

    For a typical Python install:

    Returns a boolean based on if logging was configured or not.
    """
    # TODO We should probably revisit this. Does it make more sense as
    # a method within the Client class? The Client object could easily
    # pass itself into LoggingHandler and we could eliminate args altogether.
    logger = logging.getLogger()
    if handler.__class__ in map(type, logger.handlers):
        return False

    logger.addHandler(handler)

    return True
