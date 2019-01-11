from __future__ import absolute_import

import logging

import mock

from elasticapm.conf import (
    Config,
    RegexValidator,
    _BoolConfigValue,
    _ConfigBase,
    _ConfigValue,
    _ListConfigValue,
    duration_validator,
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
    assert config.api_request_time == 5000


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
        assert config.api_request_time == 5000
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
    assert config.api_request_time == 5000


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
        millisecond = _ConfigValue("MS", type=int, validators=[duration_validator])
        second = _ConfigValue("S", type=int, validators=[duration_validator])
        minute = _ConfigValue("M", type=int, validators=[duration_validator])
        wrong_pattern = _ConfigValue("WRONG_PATTERN", type=int, validators=[duration_validator])

    c = MyConfig({"MS": "-10ms", "S": "5s", "M": "17m", "WRONG_PATTERN": "5 ms"})
    assert c.millisecond == -10
    assert c.second == 5 * 1000
    assert c.minute == 17 * 1000 * 60
    assert c.wrong_pattern is None
    assert "WRONG_PATTERN" in c.errors


def test_chained_validators():
    class MyConfig(_ConfigBase):
        chained = _ConfigValue("CHAIN", validators=[lambda val, field: val.upper(), lambda val, field: val * 2])

    c = MyConfig({"CHAIN": "x"})
    assert c.chained == "XX"
