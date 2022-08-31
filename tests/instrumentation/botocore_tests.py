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

boto3 = pytest.importorskip("boto3")


pytestmark = [pytest.mark.boto3]

os.environ["AWS_ACCESS_KEY_ID"] = "key"
os.environ["AWS_SECRET_ACCESS_KEY"] = "secret"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

LOCALSTACK_ENDPOINT = os.environ.get("AWS_URL", None)

from boto3.dynamodb.types import TypeSerializer

dynamodb_serializer = TypeSerializer()

if not LOCALSTACK_ENDPOINT:
    pytestmark.append(pytest.mark.skip("Skipping botocore tests, no AWS_URL environment variable set"))

LOCALSTACK_ENDPOINT_URL = urllib.parse.urlparse(LOCALSTACK_ENDPOINT)


@pytest.fixture()
def dynamodb():
    db = boto3.client("dynamodb", endpoint_url=LOCALSTACK_ENDPOINT)
    db.create_table(
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
    db.delete_table(TableName="Movies")


@pytest.fixture()
def sqs_client_and_queue():
    sqs = boto3.client("sqs", endpoint_url=LOCALSTACK_ENDPOINT)
    response = sqs.create_queue(QueueName="myqueue", Attributes={"MessageRetentionPeriod": "86400"})
    queue_url = response["QueueUrl"]
    yield sqs, queue_url
    sqs.delete_queue(QueueUrl=queue_url)


def test_botocore_instrumentation(instrument, elasticapm_client):
    elasticapm_client.begin_transaction("transaction.test")
    ec2 = boto3.client("ec2", endpoint_url=LOCALSTACK_ENDPOINT)
    ec2.describe_instances()
    elasticapm_client.end_transaction("MyView")
    span = elasticapm_client.events[constants.SPAN][0]

    assert span["name"] == "EC2:DescribeInstances"
    assert span["type"] == "aws"
    assert span["subtype"] == "ec2"
    assert span["action"] == "DescribeInstances"
    assert span["context"]["http"]["request"]["id"]


def test_s3(instrument, elasticapm_client):
    client = boto3.client("s3", endpoint_url=LOCALSTACK_ENDPOINT)
    elasticapm_client.begin_transaction("test")
    client.create_bucket(Bucket="xyz")
    client.put_object(Bucket="xyz", Key="abc", Body=b"foo")
    client.list_objects(Bucket="xyz")
    elasticapm_client.end_transaction("test", "test")
    transaction = elasticapm_client.end_transaction("test", "test")
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
        assert span["context"]["http"]["request"]["id"]
    assert spans[0]["name"] == "S3 CreateBucket xyz"
    assert spans[0]["action"] == "CreateBucket"
    assert spans[1]["name"] == "S3 PutObject xyz"
    assert spans[1]["action"] == "PutObject"
    assert spans[2]["name"] == "S3 ListObjects xyz"
    assert spans[2]["action"] == "ListObjects"


def test_dynamodb(instrument, elasticapm_client, dynamodb):
    elasticapm_client.begin_transaction("test")
    response = dynamodb.put_item(
        TableName="Movies",
        Item={"title": dynamodb_serializer.serialize("Independence Day"), "year": dynamodb_serializer.serialize(1994)},
    )
    assert response["ResponseMetadata"]["HTTPStatusCode"] == 200

    response = dynamodb.query(
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

    response = dynamodb.delete_item(
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
        assert span["context"]["http"]["request"]["id"]
    assert spans[0]["name"] == "DynamoDB PutItem Movies"
    assert spans[1]["name"] == "DynamoDB Query Movies"
    assert spans[1]["context"]["db"]["statement"] == "title = :v1 and #y = :v2"
    assert spans[2]["name"] == "DynamoDB DeleteItem Movies"


def test_sns(instrument, elasticapm_client):
    sns = boto3.client("sns", endpoint_url=LOCALSTACK_ENDPOINT)
    elasticapm_client.begin_transaction("test")
    response = sns.create_topic(Name="mytopic")
    topic_arn = response["TopicArn"]
    response = sns.list_topics()
    sns.publish(TopicArn=topic_arn, Subject="Saying", Message="this is my message to you-ou-ou")
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
    assert spans[2]["context"]["http"]["request"]["id"]


def test_sqs_send(instrument, elasticapm_client, sqs_client_and_queue):
    sqs, queue_url = sqs_client_and_queue
    elasticapm_client.begin_transaction("test")
    sqs.send_message(
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
    assert span["context"]["http"]["request"]["id"]

    messages = sqs.receive_message(
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


def test_sqs_send_batch(instrument, elasticapm_client, sqs_client_and_queue):
    sqs, queue_url = sqs_client_and_queue
    elasticapm_client.begin_transaction("test")
    response = sqs.send_message_batch(
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
    messages = sqs.receive_message(
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


def test_sqs_no_message_attributes(instrument, elasticapm_client, sqs_client_and_queue):
    sqs, queue_url = sqs_client_and_queue
    elasticapm_client.begin_transaction("test")
    response = sqs.send_message_batch(
        QueueUrl=queue_url,
        Entries=[
            {
                "Id": "foo",
                "MessageBody": "foo",
            },
        ],
    )
    transaction = elasticapm_client.end_transaction("test", "test")
    span = elasticapm_client.events[constants.SPAN][0]
    messages = sqs.receive_message(
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


def test_sqs_send_too_many_attributes_for_disttracing(instrument, elasticapm_client, sqs_client_and_queue, caplog):
    sqs, queue_url = sqs_client_and_queue
    attributes = {str(i): {"DataType": "String", "StringValue": str(i)} for i in range(SQS_MAX_ATTRIBUTES)}
    elasticapm_client.begin_transaction("test")
    with caplog.at_level("INFO"):
        sqs.send_message(
            QueueUrl=queue_url,
            MessageAttributes=attributes,
            MessageBody=("bar"),
        )
    elasticapm_client.end_transaction("test", "test")
    messages = sqs.receive_message(
        QueueUrl=queue_url,
        AttributeNames=["All"],
        MessageAttributeNames=[
            "All",
        ],
    )
    message = messages["Messages"][0]
    assert "traceparent" not in message["MessageAttributes"]
    assert_any_record_contains(caplog.records, "Not adding disttracing headers")


def test_sqs_send_disttracing_dropped_span(instrument, elasticapm_client, sqs_client_and_queue):
    sqs, queue_url = sqs_client_and_queue
    elasticapm_client.begin_transaction("test")
    with elasticapm.capture_span("test", leaf=True):
        sqs.send_message(
            QueueUrl=queue_url,
            MessageAttributes={
                "Title": {"DataType": "String", "StringValue": "foo"},
            },
            MessageBody=("bar"),
        )
    transaction = elasticapm_client.end_transaction("test", "test")
    assert len(elasticapm_client.events[constants.SPAN]) == 1
    messages = sqs.receive_message(
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


def test_sqs_receive_and_delete(instrument, elasticapm_client, sqs_client_and_queue):
    sqs, queue_url = sqs_client_and_queue
    sqs.send_message(
        QueueUrl=queue_url,
        MessageAttributes={
            "Title": {"DataType": "String", "StringValue": "foo"},
        },
        MessageBody=("bar"),
    )
    elasticapm_client.begin_transaction("test")
    response = sqs.receive_message(
        QueueUrl=queue_url,
        AttributeNames=["All"],
        MessageAttributeNames=[
            "All",
        ],
    )
    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=response["Messages"][0]["ReceiptHandle"])
    elasticapm_client.end_transaction("test", "test")

    receive_span = elasticapm_client.events[constants.SPAN][0]
    assert receive_span["name"] == "SQS RECEIVE from myqueue"
    assert receive_span["type"] == "messaging"
    assert receive_span["subtype"] == "sqs"
    assert receive_span["action"] == "receive"
    assert receive_span["context"]["destination"]["cloud"]["region"] == "us-east-1"
    assert receive_span["context"]["destination"]["service"]["name"] == "sqs"
    assert receive_span["context"]["destination"]["service"]["resource"] == "sqs/myqueue"
    assert receive_span["context"]["destination"]["service"]["type"] == "messaging"

    delete_span = elasticapm_client.events[constants.SPAN][1]
    assert delete_span["name"] == "SQS DELETE from myqueue"
    assert delete_span["type"] == "messaging"
    assert delete_span["subtype"] == "sqs"
    assert delete_span["action"] == "delete"
    assert delete_span["context"]["destination"]["cloud"]["region"] == "us-east-1"
    assert delete_span["context"]["destination"]["service"]["name"] == "sqs"
    assert delete_span["context"]["destination"]["service"]["resource"] == "sqs/myqueue"
    assert delete_span["context"]["destination"]["service"]["type"] == "messaging"


def test_sqs_delete_batch(instrument, elasticapm_client, sqs_client_and_queue):
    sqs, queue_url = sqs_client_and_queue
    sqs.send_message(
        QueueUrl=queue_url,
        MessageAttributes={
            "Title": {"DataType": "String", "StringValue": "foo"},
        },
        MessageBody=("bar"),
    )
    response = sqs.receive_message(
        QueueUrl=queue_url,
        AttributeNames=["All"],
        MessageAttributeNames=[
            "All",
        ],
    )
    elasticapm_client.begin_transaction("test")
    sqs.delete_message_batch(
        QueueUrl=queue_url,
        Entries=[{"Id": "foo", "ReceiptHandle": response["Messages"][0]["ReceiptHandle"]}],
    )
    elasticapm_client.end_transaction("test", "test")

    delete_span = elasticapm_client.events[constants.SPAN][0]
    assert delete_span["name"] == "SQS DELETE_BATCH from myqueue"
    assert delete_span["type"] == "messaging"
    assert delete_span["subtype"] == "sqs"
    assert delete_span["action"] == "delete_batch"
    assert delete_span["context"]["destination"]["cloud"]["region"] == "us-east-1"
    assert delete_span["context"]["destination"]["service"]["name"] == "sqs"
    assert delete_span["context"]["destination"]["service"]["resource"] == "sqs/myqueue"
    assert delete_span["context"]["destination"]["service"]["type"] == "messaging"


def test_sqs_receive_message_span_links(instrument, elasticapm_client, sqs_client_and_queue):
    sqs, queue_url = sqs_client_and_queue
    send_transaction = elasticapm_client.begin_transaction("test")
    sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=("bar"),
    )
    elasticapm_client.end_transaction("test")
    receive_transaction = elasticapm_client.begin_transaction("test")
    response = sqs.receive_message(
        QueueUrl=queue_url,
        AttributeNames=["All"],
    )
    assert len(response["Messages"]) == 1
    elasticapm_client.end_transaction("test")
    send_span = elasticapm_client.events[constants.SPAN][0]
    receive_span = elasticapm_client.events[constants.SPAN][1]
    assert receive_span["links"][0]["trace_id"] == send_transaction.trace_parent.trace_id
    assert receive_span["links"][0]["span_id"] == send_span["id"]
