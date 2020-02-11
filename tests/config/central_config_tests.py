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

import mock
import pytest


@mock.patch("tests.fixtures.DummyTransport.get_config")
def test_update_config(mock_get_config, elasticapm_client):
    assert elasticapm_client.config.transaction_sample_rate == 1.0
    assert elasticapm_client.config.config_version is None
    mock_get_config.return_value = 2, {"transaction_sample_rate": 0.1}, 30
    elasticapm_client.config.update_config()
    assert elasticapm_client.config.transaction_sample_rate == 0.1
    assert elasticapm_client.config.config_version == 2


@mock.patch("tests.fixtures.DummyTransport.get_config")
def test_environment_doesnt_override_central_config(mock_get_config, elasticapm_client):
    assert elasticapm_client.config.transaction_sample_rate == 1.0
    assert elasticapm_client.config.config_version is None
    mock_get_config.return_value = 2, {"transaction_sample_rate": 0.1}, 30
    with mock.patch.dict("os.environ", {"ELASTIC_APM_TRANSACTION_SAMPLE_RATE": "0.5"}):
        elasticapm_client.config.update_config()
    assert elasticapm_client.config.transaction_sample_rate == 0.1
    assert elasticapm_client.config.config_version == 2


@pytest.mark.parametrize("elasticapm_client", [{"transaction_sample_rate": 0.9}], indirect=True)
@mock.patch("tests.fixtures.DummyTransport.get_config")
def test_reset_to_original(mock_get_config, elasticapm_client):
    assert elasticapm_client.config.transaction_sample_rate == 0.9
    assert elasticapm_client.config.config_version is None
    assert not elasticapm_client.config.changed
    mock_get_config.return_value = 2, {"transaction_sample_rate": 0.1}, 30
    elasticapm_client.config.update_config()
    assert elasticapm_client.config.changed
    assert elasticapm_client.config.transaction_sample_rate == 0.1
    mock_get_config.return_value = 3, {}, 30
    elasticapm_client.config.update_config()
    assert not elasticapm_client.config.changed
    assert elasticapm_client.config.transaction_sample_rate == 0.9


@pytest.mark.parametrize("elasticapm_client", [{"transaction_sample_rate": 0.9}], indirect=True)
@mock.patch("tests.fixtures.DummyTransport.get_config")
def test_no_reset_if_version_matches(mock_get_config, elasticapm_client):
    assert elasticapm_client.config.transaction_sample_rate == 0.9
    assert elasticapm_client.config.config_version is None
    assert not elasticapm_client.config.changed
    mock_get_config.return_value = 2, {"transaction_sample_rate": 0.1}, 30
    elasticapm_client.config.update_config()
    assert elasticapm_client.config.changed
    assert elasticapm_client.config.transaction_sample_rate == 0.1
    mock_get_config.return_value = 2, {}, 30
    elasticapm_client.config.update_config()
    assert elasticapm_client.config.changed
    assert elasticapm_client.config.config_version == 2


@pytest.mark.parametrize("elasticapm_client", [{"central_config": False}], indirect=True)
def test_disable_central_config(elasticapm_client):
    assert elasticapm_client._config_updater is None


@mock.patch("tests.fixtures.DummyTransport.get_config")
def test_erroneous_config_is_ignored(mock_get_config, elasticapm_client):
    assert elasticapm_client.config.transaction_sample_rate == 1.0
    assert elasticapm_client.config.config_version is None
    mock_get_config.return_value = 2, {"transaction_sample_rate": "x"}, 30
    elasticapm_client.config.update_config()
    assert elasticapm_client.config.transaction_sample_rate == 1.0
    assert elasticapm_client.config.config_version == None
