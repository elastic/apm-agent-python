import pytest  # isort:skip
pytest.importorskip("boto3")  # isort:skip

import boto3
import mock

from elasticapm.instrumentation.packages.botocore import BotocoreInstrumentation

pytestmark = pytest.mark.boto3


@mock.patch("botocore.endpoint.Endpoint.make_request")
def test_botocore_instrumentation(mock_make_request, instrument, elasticapm_client):
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_make_request.return_value = (mock_response, {})

    elasticapm_client.begin_transaction("transaction.test")
    session = boto3.Session(aws_access_key_id='foo',
                            aws_secret_access_key='bar',
                            region_name='us-west-2')
    ec2 = session.client('ec2')
    ec2.describe_instances()
    transaction = elasticapm_client.end_transaction("MyView")
    span = transaction.spans[0]

    assert span.name == 'ec2:DescribeInstances'
    assert span.context['service'] == 'ec2'
    assert span.context['region'] == 'us-west-2'
    assert span.context['operation'] == 'DescribeInstances'


def test_nonstandard_endpoint_url(instrument, elasticapm_client):
    instrument = BotocoreInstrumentation()
    elasticapm_client.begin_transaction('test')
    module, method = BotocoreInstrumentation.instrument_list[0]
    instance = mock.Mock(_endpoint=mock.Mock(host='https://example'))
    instrument.call(module, method, lambda *args, **kwargs: None, instance,
                    ('DescribeInstances',), {})
    transaction = elasticapm_client.end_transaction('test', 'test')
    span = transaction.spans[0]

    assert span.name == 'example:DescribeInstances'
    assert span.context['service'] == 'example'
    assert span.context['region'] is None
    assert span.context['operation'] == 'DescribeInstances'
