import boto3
import mock

from elasticapm.traces import trace


@mock.patch("botocore.endpoint.Endpoint.make_request")
def test_botocore_instrumentation(mock_make_request, elasticapm_client):
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_make_request.return_value = (mock_response, {})

    elasticapm_client.begin_transaction("transaction.test")
    with trace("test_pipeline", "test"):
        session = boto3.Session(aws_access_key_id='foo',
                                aws_secret_access_key='bar',
                                region_name='us-west-2')
        ec2 = session.client('ec2')
        ec2.describe_instances()
    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.instrumentation_store.get_all()
    traces = transactions[0]['traces']
    assert 'ec2:DescribeInstances' in map(lambda x: x['name'], traces)
