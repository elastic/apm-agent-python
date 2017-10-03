import boto3
import mock

from elasticapm.traces import trace
from tests.fixtures import test_client


@mock.patch("botocore.endpoint.Endpoint.make_request")
def test_botocore_instrumentation(mock_make_request, test_client):
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_make_request.return_value = (mock_response, {})

    test_client.begin_transaction("transaction.test")
    with trace("test_pipeline", "test"):
        session = boto3.Session(aws_access_key_id='foo',
                                aws_secret_access_key='bar',
                                region_name='us-west-2')
        ec2 = session.client('ec2')
        ec2.describe_instances()
    test_client.end_transaction("MyView")

    transactions = test_client.instrumentation_store.get_all()
    traces = transactions[0]['traces']
    assert 'ec2:DescribeInstances' in map(lambda x: x['name'], traces)
