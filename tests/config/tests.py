#  BSD 3-Clause License
#
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
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from __future__ import absolute_import

import logging
import os
import platform
import stat
from datetime import timedelta

import mock
import pytest

from elasticapm.conf import (
    Config,
    ConfigurationError,
    EnumerationValidator,
    FileIsReadableValidator,
    PrecisionValidator,
    RegexValidator,
    VersionedConfig,
    _BoolConfigValue,
    _ConfigBase,
    _ConfigValue,
    _DictConfigValue,
    _DurationConfigValue,
    _ListConfigValue,
    constants,
    setup_logging,
    size_validator,
)


def test_basic_not_configured():
    with mock.patch("logging.getLogger", spec=logging.getLogger) as getLogger:
        logger = getLogger()
        logger.handlers = []
        handler = mock.Mock()
        result = setup_logging(handler)
        assert result


def test_basic_already_configured():
    with mock.patch("logging.getLogger", spec=logging.getLogger) as getLogger:
        handler = mock.Mock()
        logger = getLogger()
        logger.handlers = [handler]
        result = setup_logging(handler)
        assert not result


def test_config_dict():
    config = Config(
        {
            "SERVICE_NAME": "foo",
            "SECRET_TOKEN": "bar",
            "SERVER_URL": "http://example.com:1234",
            "SERVICE_VERSION": 1,
            "HOSTNAME": "localhost",
            "API_REQUEST_TIME": "5s",
        }
    )

    assert config.service_name == "foo"
    assert config.secret_token == "bar"
    assert config.server_url == "http://example.com:1234"
    assert config.service_version == "1"
    assert config.hostname == "localhost"
    assert config.api_request_time.total_seconds() == 5


def test_config_environment():
    with mock.patch.dict(
        "os.environ",
        {
            "ELASTIC_APM_SERVICE_NAME": "foo",
            "ELASTIC_APM_SECRET_TOKEN": "bar",
            "ELASTIC_APM_SERVER_URL": "http://example.com:1234",
            "ELASTIC_APM_SERVICE_VERSION": "1",
            "ELASTIC_APM_HOSTNAME": "localhost",
            "ELASTIC_APM_API_REQUEST_TIME": "5s",
            "ELASTIC_APM_AUTO_LOG_STACKS": "false",
        },
    ):
        config = Config()

        assert config.service_name == "foo"
        assert config.secret_token == "bar"
        assert config.server_url == "http://example.com:1234"
        assert config.service_version == "1"
        assert config.hostname == "localhost"
        assert config.api_request_time.total_seconds() == 5
        assert config.auto_log_stacks is False


def test_config_inline_dict():
    config = Config(
        inline_dict={
            "service_name": "foo",
            "secret_token": "bar",
            "server_url": "http://example.com:1234",
            "service_version": "1",
            "hostname": "localhost",
            "api_request_time": "5s",
        }
    )

    assert config.service_name == "foo"
    assert config.secret_token == "bar"
    assert config.server_url == "http://example.com:1234"
    assert config.service_version == "1"
    assert config.hostname == "localhost"
    assert config.api_request_time.total_seconds() == 5


def test_config_precedence():
    #  precedence order: environment, inline dict, config dict
    with mock.patch.dict("os.environ", {"ELASTIC_APM_SERVICE_NAME": "bar"}):
        config = Config(
            {"SERVICE_NAME": "foo", "SECRET_TOKEN": "secret", "COLLECT_LOCAL_VARIABLES": "all"},
            inline_dict={"secret_token": "notsecret", "service_name": "baz"},
        )

    assert config.service_name == "bar"
    assert config.secret_token == "notsecret"
    assert config.collect_local_variables == "all"


def test_list_config_value():
    class MyConfig(_ConfigBase):
        my_list = _ListConfigValue("MY_LIST", list_separator="|", type=int)

    config = MyConfig({"MY_LIST": "1|2|3"})
    assert config.my_list == [1, 2, 3]


def test_dict_config_value():
    class MyConfig(_ConfigBase):
        my_dict = _DictConfigValue("MY_DICT")
        my_typed_dict = _DictConfigValue("MY_TYPED_DICT", type=int)
        my_native_dict = _DictConfigValue("MY_NATIVE_DICT")

    config = MyConfig(
        {"MY_DICT": "a=b, c = d ,e=f", "MY_TYPED_DICT": "a=1,b=2"}, inline_dict={"my_native_dict": {"x": "y"}}
    )
    assert config.my_dict == {"a": "b", "c": "d", "e": "f"}
    assert config.my_typed_dict == {"a": 1, "b": 2}
    assert config.my_native_dict == {"x": "y"}


def test_bool_config_value():
    class MyConfig(_ConfigBase):
        my_bool = _BoolConfigValue("MY_BOOL", true_string="yup", false_string="nope")

    config = MyConfig({"MY_BOOL": "yup"})

    assert config.my_bool is True

    config.my_bool = "nope"

    assert config.my_bool is False


def test_values_not_shared_among_instances():
    class MyConfig(_ConfigBase):
        my_bool = _BoolConfigValue("MY_BOOL", true_string="yup", false_string="nope")

    c1 = MyConfig({"MY_BOOL": "yup"})
    c2 = MyConfig({"MY_BOOL": "nope"})

    assert c1.my_bool is not c2.my_bool


def test_regex_validation():
    class MyConfig(_ConfigBase):
        my_regex = _ConfigValue("MY_REGEX", validators=[RegexValidator(r"\d+")])

    c1 = MyConfig({"MY_REGEX": "123"})
    c2 = MyConfig({"MY_REGEX": "abc"})
    assert not c1.errors
    assert "MY_REGEX" in c2.errors


def test_size_validation():
    class MyConfig(_ConfigBase):
        byte = _ConfigValue("BYTE", type=int, validators=[size_validator])
        kbyte = _ConfigValue("KBYTE", type=int, validators=[size_validator])
        mbyte = _ConfigValue("MBYTE", type=int, validators=[size_validator])
        gbyte = _ConfigValue("GBYTE", type=int, validators=[size_validator])
        wrong_pattern = _ConfigValue("WRONG_PATTERN", type=int, validators=[size_validator])

    c = MyConfig({"BYTE": "10b", "KBYTE": "5kb", "MBYTE": "17mb", "GBYTE": "2gb", "WRONG_PATTERN": "5 kb"})
    assert c.byte == 10
    assert c.kbyte == 5 * 1024
    assert c.mbyte == 17 * 1024 * 1024
    assert c.gbyte == 2 * 1024 * 1024 * 1024
    assert c.wrong_pattern is None
    assert "WRONG_PATTERN" in c.errors


def test_duration_validation():
    class MyConfig(_ConfigBase):
        microsecond = _DurationConfigValue("US", allow_microseconds=True)
        millisecond = _DurationConfigValue("MS")
        second = _DurationConfigValue("S")
        minute = _DurationConfigValue("M")
        default_unit_ms = _DurationConfigValue("DM", unitless_factor=0.001)
        wrong_pattern = _DurationConfigValue("WRONG_PATTERN")

    c = MyConfig({"US": "10us", "MS": "-10ms", "S": "5s", "M": "17m", "DM": "83", "WRONG_PATTERN": "5 ms"})
    assert c.microsecond == timedelta(microseconds=10)
    assert c.millisecond == timedelta(milliseconds=-10)
    assert c.second == timedelta(seconds=5)
    assert c.minute == timedelta(minutes=17)
    assert c.default_unit_ms == timedelta(milliseconds=83)
    assert c.wrong_pattern is None
    assert "WRONG_PATTERN" in c.errors


def test_precision_validation():
    class MyConfig(_ConfigBase):
        sample_rate = _ConfigValue("SR", type=float, validators=[PrecisionValidator(4, 0.0001)])

    c = MyConfig({"SR": "0.0000001"})
    assert c.sample_rate == 0.0001
    c = MyConfig({"SR": "0.555555"})
    assert c.sample_rate == 0.5556


def test_chained_validators():
    class MyConfig(_ConfigBase):
        chained = _ConfigValue("CHAIN", validators=[lambda val, field: val.upper(), lambda val, field: val * 2])

    c = MyConfig({"CHAIN": "x"})
    assert c.chained == "XX"


def test_file_is_readable_validator_not_exists(tmpdir):
    validator = FileIsReadableValidator()
    with pytest.raises(ConfigurationError) as e:
        validator(tmpdir.join("doesnotexist").strpath, "path")
    assert "does not exist" in e.value.args[0]


def test_file_is_readable_validator_not_a_file(tmpdir):
    validator = FileIsReadableValidator()
    with pytest.raises(ConfigurationError) as e:
        validator(tmpdir.strpath, "path")
    assert "is not a file" in e.value.args[0]


@pytest.mark.skipif(platform.system() == "Windows", reason="os.access() doesn't seem to work as we expect on Windows")
def test_file_is_readable_validator_not_readable(tmpdir):
    p = tmpdir.join("nonreadable")
    p.write("")
    os.chmod(p.strpath, stat.S_IWRITE)
    validator = FileIsReadableValidator()
    with pytest.raises(ConfigurationError) as e:
        validator(p.strpath, "path")
    assert "is not readable" in e.value.args[0]


def test_file_is_readable_validator_all_good(tmpdir):
    p = tmpdir.join("readable")
    p.write("")
    validator = FileIsReadableValidator()
    assert validator(p.strpath, "path") == p.strpath


def test_validate_catches_type_errors():
    class MyConfig(_ConfigBase):
        an_int = _ConfigValue("anint", type=int)

    c = MyConfig({"anint": "x"})
    assert "invalid literal" in c.errors["anint"]


@pytest.mark.parametrize(
    "val,expected",
    [("transactions", constants.TRANSACTION), ("errors", constants.ERROR), ("all", "all"), ("off", "off")],
)
def test_capture_body_mapping(val, expected):
    c = Config(inline_dict={"capture_body": val})
    assert c.capture_body == expected


@pytest.mark.parametrize(
    "enabled,recording,is_recording",
    [(True, True, True), (True, False, False), (False, True, False), (False, False, False)],
)
def test_is_recording(enabled, recording, is_recording):
    c = Config(inline_dict={"enabled": enabled, "recording": recording, "service_name": "foo"})
    assert c.is_recording is is_recording


def test_required_is_checked_if_field_not_provided():
    class MyConfig(_ConfigBase):
        this_one_is_required = _ConfigValue("this_one_is_required", type=int, required=True)
        this_one_isnt = _ConfigValue("this_one_isnt", type=int, required=False)

    assert MyConfig({"this_one_is_required": None}).errors
    assert MyConfig({}).errors
    assert MyConfig({"this_one_isnt": 1}).errors

    c = MyConfig({"this_one_is_required": 1})
    c.update({"this_one_isnt": 0})
    assert not c.errors


def test_callback():
    test_var = {"foo": 0}

    def set_global(dict_key, old_value, new_value, config_instance):
        # TODO make test_var `nonlocal` once we drop py2 -- it can just be a
        # basic variable then instead of a dictionary
        test_var[dict_key] += 1

    class MyConfig(_ConfigBase):
        foo = _ConfigValue("foo", callbacks=[set_global])

    c = MyConfig({"foo": "bar"})
    assert test_var["foo"] == 1
    c.update({"foo": "baz"})
    assert test_var["foo"] == 2


def test_callbacks_on_default():
    test_var = {"foo": 0}

    def set_global(dict_key, old_value, new_value, config_instance):
        # TODO make test_var `nonlocal` once we drop py2 -- it can just be a
        # basic variable then instead of a dictionary
        test_var[dict_key] += 1

    class MyConfig(_ConfigBase):
        foo = _ConfigValue("foo", callbacks=[set_global], default="foobar")

    c = MyConfig()
    assert test_var["foo"] == 1
    c = MyConfig({"foo": "bar"})
    assert test_var["foo"] == 2
    c.update({"foo": "baz"})
    assert test_var["foo"] == 3

    # Test without callback on default
    class MyConfig(_ConfigBase):
        foo = _ConfigValue("foo", callbacks=[set_global], callbacks_on_default=False, default="foobar")

    c = MyConfig()
    assert test_var["foo"] == 3
    c = MyConfig({"foo": "bar"})
    assert test_var["foo"] == 4
    c.update({"foo": "baz"})
    assert test_var["foo"] == 5


def test_callback_reset():
    test_var = {"foo": 0}

    def set_global(dict_key, old_value, new_value, config_instance):
        # TODO make test_var `nonlocal` once we drop py2 -- it can just be a
        # basic variable then instead of a dictionary
        test_var[dict_key] += 1

    class MyConfig(_ConfigBase):
        foo = _ConfigValue("foo", callbacks=[set_global])

    c = VersionedConfig(MyConfig({"foo": "bar"}), version=None)
    assert test_var["foo"] == 1
    c.update(version=2, **{"foo": "baz"})
    assert test_var["foo"] == 2
    c.reset()
    assert test_var["foo"] == 3


def test_reset_after_adding_config():
    class MyConfig(_ConfigBase):
        foo = _ConfigValue("foo")
        bar = _ConfigValue("bar")

    c = VersionedConfig(MyConfig({"foo": "baz"}), version=1)

    c.update(version=2, bar="bazzinga")

    c.reset()
    assert c.bar is None


def test_valid_values_validator():
    # Case sensitive
    v = EnumerationValidator(["foo", "Bar", "baz"], case_sensitive=False)
    assert v("foo", "foo") == "foo"
    assert v("bar", "foo") == "Bar"
    assert v("BAZ", "foo") == "baz"
    with pytest.raises(ConfigurationError):
        v("foobar", "foo")

    # Case insensitive
    v = EnumerationValidator(["foo", "Bar", "baz"], case_sensitive=True)
    assert v("foo", "foo") == "foo"
    with pytest.raises(ConfigurationError):
        v("bar", "foo")
    with pytest.raises(ConfigurationError):
        v("BAZ", "foo")
    assert v("Bar", "foo") == "Bar"
    with pytest.raises(ConfigurationError):
        v("foobar", "foo")


def test_versioned_config_attribute_access(elasticapm_client):
    # see https://github.com/elastic/apm-agent-python/issues/1147
    val = elasticapm_client.config.start_stop_order
    assert isinstance(val, int)
    # update config to ensure start_stop_order isn't read from the proxied Config object
    elasticapm_client.config.update("2", capture_body=True)
    val = elasticapm_client.config.start_stop_order
    assert isinstance(val, int)


def test_config_all_upper_case():
    c = Config.__class__.__dict__.items()
    for field, config_value in Config.__dict__.items():
        if not isinstance(config_value, _ConfigValue):
            continue
        assert config_value.env_key == config_value.env_key.upper()
