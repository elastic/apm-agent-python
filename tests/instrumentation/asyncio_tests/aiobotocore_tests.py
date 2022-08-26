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
import os
import urllib.parse

import pytest

import elasticapm
from elasticapm.conf import constants
from elasticapm.instrumentation.packages.botocore import SQS_MAX_ATTRIBUTES
from tests.utils import assert_any_record_contains

aiosession = pytest.importorskip("aiobotocore.session")


pytestmark = [pytest.mark.asyncio, pytest.mark.aiobotocore]

os.environ["AWS_ACCESS_KEY_ID"] = "key"
os.environ["AWS_SECRET_ACCESS_KEY"] = "secret"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

LOCALSTACK_ENDPOINT = os.environ.get("AWS_URL", None)

from boto3.dynamodb.types import TypeSerializer

dynamodb_serializer = TypeSerializer()

if not LOCALSTACK_ENDPOINT:
    pytestmark.append(pytest.mark.skip("Skipping aiobotocore tests, no AWS_URL environment variable set"))

LOCALSTACK_ENDPOINT_URL = urllib.parse.urlparse(LOCALSTACK_ENDPOINT)


@pytest.fixture()
def session():
    return aiosession.get_session()


@pytest.fixture()
async def dynamodb(session):
    async with session.create_client("dynamodb", endpoint_url=LOCALSTACK_ENDPOINT) as db:
        await db.create_table(
            TableName="Movies",
            KeySchema=[
                {"AttributeName": "year", "KeyType": "HASH"},  # Partition key
                {"AttributeName": "title", "KeyType": "RANGE"},  # Sort key
            ],
            AttributeDefinitions=[
                {"AttributeName": "year", "AttributeType": "N"},
                {"AttributeName": "title", "AttributeType": "S"},
            ],
            ProvisionedThroughput={"ReadCapacityUnits": 10, "WriteCapacityUnits": 10},
        )
        yield db
        await db.delete_table(TableName="Movies")


@pytest.fixture()
async def sqs_client_and_queue(session):
    async with session.create_client("sqs", endpoint_url=LOCALSTACK_ENDPOINT) as sqs:
        response = await sqs.create_queue(QueueName="myqueue", Attributes={"MessageRetentionPeriod": "86400"})
        queue_url = response["QueueUrl"]
        yield sqs, queue_url
        await sqs.delete_queue(QueueUrl=queue_url)


async def test_botocore_instrumentation(instrument, elasticapm_client, session):
    elasticapm_client.begin_transaction("transaction.test")
    async with session.create_client("ec2", endpoint_url=LOCALSTACK_ENDPOINT) as ec2:
        await ec2.describe_instances()
        elasticapm_client.end_transaction("MyView")
    span = elasticapm_client.events[constants.SPAN][0]

    assert span["name"] == "EC2:DescribeInstances"
    assert span["type"] == "aws"
    assert span["subtype"] == "ec2"
    assert span["action"] == "DescribeInstances"


async def test_s3(instrument, elasticapm_client, session):
    async with session.create_client("s3", endpoint_url=LOCALSTACK_ENDPOINT) as client:
        elasticapm_client.begin_transaction("test")
        await client.create_bucket(Bucket="xyz")
        await client.put_object(Bucket="xyz", Key="abc", Body=b"foo")
        await client.list_objects(Bucket="xyz")
        elasticapm_client.end_transaction("test", "test")
    spans = elasticapm_client.events[constants.SPAN]
    for span in spans:
        assert span["type"] == "storage"
        assert span["subtype"] == "s3"
        assert span["context"]["destination"]["address"] == LOCALSTACK_ENDPOINT_URL.hostname
        assert span["context"]["destination"]["port"] == LOCALSTACK_ENDPOINT_URL.port
        assert span["context"]["destination"]["cloud"]["region"] == "us-east-1"
        assert span["context"]["destination"]["service"]["name"] == "s3"
        assert span["context"]["destination"]["service"]["resource"] == "xyz"
        assert span["context"]["destination"]["service"]["type"] == "storage"
    assert spans[0]["name"] == "S3 CreateBucket xyz"
    assert spans[0]["action"] == "CreateBucket"
    assert spans[1]["name"] == "S3 PutObject xyz"
    assert spans[1]["action"] == "PutObject"
    assert spans[2]["name"] == "S3 ListObjects xyz"
    assert spans[2]["action"] == "ListObjects"


async def test_dynamodb(instrument, elasticapm_client, dynamodb):
    elasticapm_client.begin_transaction("test")
    response = await dynamodb.put_item(
        TableName="Movies",
        Item={"title": dynamodb_serializer.serialize("Independence Day"), "year": dynamodb_serializer.serialize(1994)},
    )
    assert response["ResponseMetadata"]["HTTPStatusCode"] == 200

    response = await dynamodb.query(
        TableName="Movies",
        ExpressionAttributeValues={
            ":v1": {
                "S": "Independence Day",
            },
            ":v2": {
                "N": "1994",
            },
        },
        ExpressionAttributeNames={"#y": "year"},
        KeyConditionExpression="title = :v1 and #y = :v2",
    )
    assert response["ResponseMetadata"]["HTTPStatusCode"] == 200

    response = await dynamodb.delete_item(
        TableName="Movies",
        Key={
            "title": {
                "S": '"Independence Day"',
            },
            "year": {
                "N": "1994",
            },
        },
    )
    assert response["ResponseMetadata"]["HTTPStatusCode"] == 200

    elasticapm_client.end_transaction("test", "test")
    spans = elasticapm_client.events[constants.SPAN]
    for span in spans:
        assert span["type"] == "db"
        assert span["subtype"] == "dynamodb"
        assert span["action"] == "query"
        assert span["context"]["db"]["instance"] == "us-east-1"
        assert span["context"]["db"]["type"] == "dynamodb"
        assert span["context"]["destination"]["address"] == LOCALSTACK_ENDPOINT_URL.hostname
        assert span["context"]["destination"]["port"] == LOCALSTACK_ENDPOINT_URL.port
        assert span["context"]["destination"]["cloud"]["region"] == "us-east-1"
        assert span["context"]["destination"]["service"]["name"] == "dynamodb"
        assert span["context"]["destination"]["service"]["resource"] == "Movies"
        assert span["context"]["destination"]["service"]["type"] == "db"
    assert spans[0]["name"] == "DynamoDB PutItem Movies"
    assert spans[1]["name"] == "DynamoDB Query Movies"
    assert spans[1]["context"]["db"]["statement"] == "title = :v1 and #y = :v2"
    assert spans[2]["name"] == "DynamoDB DeleteItem Movies"


async def test_sns(instrument, elasticapm_client, session):
    async with session.create_client("sns", endpoint_url=LOCALSTACK_ENDPOINT) as sns:
        elasticapm_client.begin_transaction("test")
        response = await sns.create_topic(Name="mytopic")
        topic_arn = response["TopicArn"]
        await sns.list_topics()
        await sns.publish(TopicArn=topic_arn, Subject="Saying", Message="this is my message to you-ou-ou")
        elasticapm_client.end_transaction("test", "test")
    spans = elasticapm_client.events[constants.SPAN]
    assert spans[2]["name"] == "SNS Publish mytopic"
    assert spans[2]["type"] == "messaging"
    assert spans[2]["subtype"] == "sns"
    assert spans[2]["action"] == "send"
    assert spans[2]["context"]["destination"]["address"] == LOCALSTACK_ENDPOINT_URL.hostname
    assert spans[2]["context"]["destination"]["port"] == LOCALSTACK_ENDPOINT_URL.port
    assert spans[2]["context"]["destination"]["cloud"]["region"] == "us-east-1"
    assert spans[2]["context"]["destination"]["service"]["name"] == "sns"
    assert spans[2]["context"]["destination"]["service"]["resource"] == "sns/mytopic"
    assert spans[2]["context"]["destination"]["service"]["type"] == "messaging"


async def test_sqs_send(instrument, elasticapm_client, sqs_client_and_queue):
    sqs, queue_url = sqs_client_and_queue
    elasticapm_client.begin_transaction("test")
    await sqs.send_message(
        QueueUrl=queue_url,
        MessageAttributes={
            "Title": {"DataType": "String", "StringValue": "foo"},
        },
        MessageBody=("bar"),
    )
    transaction = elasticapm_client.end_transaction("test", "test")
    span = elasticapm_client.events[constants.SPAN][0]
    assert span["name"] == "SQS SEND to myqueue"
    assert span["type"] == "messaging"
    assert span["subtype"] == "sqs"
    assert span["action"] == "send"
    assert span["context"]["destination"]["cloud"]["region"] == "us-east-1"
    assert span["context"]["destination"]["service"]["name"] == "sqs"
    assert span["context"]["destination"]["service"]["resource"] == "sqs/myqueue"
    assert span["context"]["destination"]["service"]["type"] == "messaging"

    messages = await sqs.receive_message(
        QueueUrl=queue_url,
        AttributeNames=["All"],
        MessageAttributeNames=[
            "All",
        ],
    )
    message = messages["Messages"][0]
    assert "traceparent" in message["MessageAttributes"]
    traceparent = message["MessageAttributes"]["traceparent"]["StringValue"]
    assert transaction.trace_parent.trace_id in traceparent
    assert span["id"] in traceparent


async def test_sqs_send_batch(instrument, elasticapm_client, sqs_client_and_queue):
    sqs, queue_url = sqs_client_and_queue
    elasticapm_client.begin_transaction("test")
    await sqs.send_message_batch(
        QueueUrl=queue_url,
        Entries=[
            {
                "Id": "foo",
                "MessageBody": "foo",
                "MessageAttributes": {"string": {"StringValue": "foo", "DataType": "String"}},
            },
        ],
    )
    transaction = elasticapm_client.end_transaction("test", "test")
    span = elasticapm_client.events[constants.SPAN][0]
    assert span["name"] == "SQS SEND_BATCH to myqueue"
    assert span["type"] == "messaging"
    assert span["subtype"] == "sqs"
    assert span["action"] == "send_batch"
    assert span["context"]["destination"]["cloud"]["region"] == "us-east-1"
    assert span["context"]["destination"]["service"]["name"] == "sqs"
    assert span["context"]["destination"]["service"]["resource"] == "sqs/myqueue"
    assert span["context"]["destination"]["service"]["type"] == "messaging"
    messages = await sqs.receive_message(
        QueueUrl=queue_url,
        AttributeNames=["All"],
        MessageAttributeNames=[
            "All",
        ],
    )
    message = messages["Messages"][0]
    assert "traceparent" in message["MessageAttributes"]
    traceparent = message["MessageAttributes"]["traceparent"]["StringValue"]
    assert transaction.trace_parent.trace_id in traceparent
    assert span["id"] in traceparent


async def test_sqs_send_too_many_attributes_for_disttracing(
    instrument, elasticapm_client, sqs_client_and_queue, caplog
):
    sqs, queue_url = sqs_client_and_queue
    attributes = {str(i): {"DataType": "String", "StringValue": str(i)} for i in range(SQS_MAX_ATTRIBUTES)}
    elasticapm_client.begin_transaction("test")
    with caplog.at_level("INFO"):
        await sqs.send_message(
            QueueUrl=queue_url,
            MessageAttributes=attributes,
            MessageBody=("bar"),
        )
    elasticapm_client.end_transaction("test", "test")
    messages = await sqs.receive_message(
        QueueUrl=queue_url,
        AttributeNames=["All"],
        MessageAttributeNames=[
            "All",
        ],
    )
    message = messages["Messages"][0]
    assert "traceparent" not in message["MessageAttributes"]
    assert_any_record_contains(caplog.records, "Not adding disttracing headers")


async def test_sqs_send_disttracing_dropped_span(instrument, elasticapm_client, sqs_client_and_queue):
    sqs, queue_url = sqs_client_and_queue
    elasticapm_client.begin_transaction("test")
    with elasticapm.capture_span("test", leaf=True):
        await sqs.send_message(
            QueueUrl=queue_url,
            MessageAttributes={
                "Title": {"DataType": "String", "StringValue": "foo"},
            },
            MessageBody=("bar"),
        )
    transaction = elasticapm_client.end_transaction("test", "test")
    assert len(elasticapm_client.events[constants.SPAN]) == 1
    messages = await sqs.receive_message(
        QueueUrl=queue_url,
        AttributeNames=["All"],
        MessageAttributeNames=[
            "All",
        ],
    )
    message = messages["Messages"][0]
    assert "traceparent" in message["MessageAttributes"]
    traceparent = message["MessageAttributes"]["traceparent"]["StringValue"]
    assert transaction.trace_parent.trace_id in traceparent
    assert transaction.id in traceparent  # due to DroppedSpan, transaction.id is used instead of span.id


async def test_sqs_receive(instrument, elasticapm_client, sqs_client_and_queue):
    sqs, queue_url = sqs_client_and_queue
    await sqs.send_message(
        QueueUrl=queue_url,
        MessageAttributes={
            "Title": {"DataType": "String", "StringValue": "foo"},
        },
        MessageBody=("bar"),
    )
    elasticapm_client.begin_transaction("test")
    await sqs.receive_message(
        QueueUrl=queue_url,
        AttributeNames=["All"],
        MessageAttributeNames=[
            "All",
        ],
    )
    elasticapm_client.end_transaction("test", "test")
    span = elasticapm_client.events[constants.SPAN][0]
    assert span["name"] == "SQS RECEIVE from myqueue"
    assert span["type"] == "messaging"
    assert span["subtype"] == "sqs"
    assert span["action"] == "receive"
    assert span["context"]["destination"]["cloud"]["region"] == "us-east-1"
    assert span["context"]["destination"]["service"]["name"] == "sqs"
    assert span["context"]["destination"]["service"]["resource"] == "sqs/myqueue"
    assert span["context"]["destination"]["service"]["type"] == "messaging"
