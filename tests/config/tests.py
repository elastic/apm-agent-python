from __future__ import absolute_import

import logging

import mock

from elasticapm.conf import (Config, _BoolConfigValue, _ConfigBase,
                             _ConfigValue, _ListConfigValue, setup_logging)


def test_basic_not_configured():
    with mock.patch('logging.getLogger', spec=logging.getLogger) as getLogger:
        logger = getLogger()
        logger.handlers = []
        handler = mock.Mock()
        result = setup_logging(handler)
        assert result


def test_basic_already_configured():
    with mock.patch('logging.getLogger', spec=logging.getLogger) as getLogger:
        handler = mock.Mock()
        logger = getLogger()
        logger.handlers = [handler]
        result = setup_logging(handler)
        assert not result


def test_config_dict():
    config = Config({
        'SERVICE_NAME': 'foo',
        'SECRET_TOKEN': 'bar',
        'SERVER_URL': 'http://example.com:1234',
        'APP_VERSION': 1,
        'HOSTNAME': 'localhost',
        'TRACES_SEND_FREQ': '5'
    })

    assert config.service_name == 'foo'
    assert config.secret_token == 'bar'
    assert config.server_url == 'http://example.com:1234'
    assert config.app_version == '1'
    assert config.hostname == 'localhost'
    assert config.transaction_send_frequency == 5


def test_config_environment():
    with mock.patch.dict('os.environ', {
        'ELASTIC_APM_SERVICE_NAME': 'foo',
        'ELASTIC_APM_SECRET_TOKEN': 'bar',
        'ELASTIC_APM_SERVER_URL': 'http://example.com:1234',
        'ELASTIC_APM_APP_VERSION': '1',
        'ELASTIC_APM_HOSTNAME': 'localhost',
        'ELASTIC_APM_TRACES_SEND_FREQ': '5',
        'ELASTIC_APM_AUTO_LOG_STACKS': 'false',
    }):
        config = Config()

        assert config.service_name == 'foo'
        assert config.secret_token == 'bar'
        assert config.server_url == 'http://example.com:1234'
        assert config.app_version == '1'
        assert config.hostname == 'localhost'
        assert config.transaction_send_frequency == 5
        assert config.auto_log_stacks == False


def test_config_defaults_dict():
    config = Config(default_dict={
        'service_name': 'foo',
        'secret_token': 'bar',
        'server_url': 'http://example.com:1234',
        'app_version': '1',
        'hostname': 'localhost',
        'transaction_send_frequency': '5',
    })

    assert config.service_name == 'foo'
    assert config.secret_token == 'bar'
    assert config.server_url == 'http://example.com:1234'
    assert config.app_version == '1'
    assert config.hostname == 'localhost'
    assert config.transaction_send_frequency == 5


def test_config_precedence():
    #  precendece order: config dict, environment, default dict
    with mock.patch.dict('os.environ', {
        'ELASTIC_APM_SERVICE_NAME': 'bar',
        'ELASTIC_APM_SECRET_TOKEN': 'secret'
    }):
        config = Config({
            'SERVICE_NAME': 'foo',
        }, default_dict={'secret_token': 'notsecret'})

    assert config.service_name == 'foo'
    assert config.secret_token == 'secret'


def test_list_config_value():
    class MyConfig(_ConfigBase):
        my_list = _ListConfigValue('MY_LIST', list_separator='|', type=int)

    config = MyConfig({'MY_LIST': '1|2|3'})
    assert config.my_list == [1, 2, 3]


def test_bool_config_value():
    class MyConfig(_ConfigBase):
        my_bool = _BoolConfigValue('MY_BOOL', true_string='yup', false_string='nope')

    config = MyConfig({'MY_BOOL': 'yup'})

    assert config.my_bool is True

    config.my_bool = 'nope'

    assert config.my_bool is False


def test_values_not_shared_among_instances():
    class MyConfig(_ConfigBase):
        my_bool = _BoolConfigValue('MY_BOOL', true_string='yup', false_string='nope')

    c1 = MyConfig({'MY_BOOL': 'yup'})
    c2 = MyConfig({'MY_BOOL': 'nope'})

    assert c1.my_bool is not c2.my_bool
