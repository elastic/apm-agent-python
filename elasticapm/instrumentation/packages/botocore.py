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

from collections import namedtuple

from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.traces import capture_span
from elasticapm.utils.compat import urlparse

HandlerInfo = namedtuple("HandlerInfo", ("signature", "span_type", "span_subtype", "span_action", "context"))

# Used for boto3 < 1.7
endpoint_to_service_id = {"SNS": "SNS", "S3": "S3", "DYNAMODB": "DynamoDB", "SQS": "SQS"}


class BotocoreInstrumentation(AbstractInstrumentedModule):
    name = "botocore"

    instrument_list = [("botocore.client", "BaseClient._make_api_call")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        if "operation_name" in kwargs:
            operation_name = kwargs["operation_name"]
        else:
            operation_name = args[0]

        service_model = instance.meta.service_model
        if hasattr(service_model, "service_id"):  # added in boto3 1.7
            service = service_model.service_id
        else:
            service = service_model.service_name.upper()
            service = endpoint_to_service_id.get(service, service)

        parsed_url = urlparse.urlparse(instance.meta.endpoint_url)
        context = {
            "destination": {
                "address": parsed_url.hostname,
                "port": parsed_url.port,
                "cloud": {"region": instance.meta.region_name},
            }
        }

        handler_info = None
        handler = handlers.get(service, False)
        if handler:
            handler_info = handler(operation_name, service, instance, args, kwargs, context)
        if not handler_info:
            handler_info = handle_default(operation_name, service, instance, args, kwargs, context)

        with capture_span(
            handler_info.signature,
            span_type=handler_info.span_type,
            leaf=True,
            span_subtype=handler_info.span_subtype,
            span_action=handler_info.span_action,
            extra=handler_info.context,
        ):
            return wrapped(*args, **kwargs)


def handle_s3(operation_name, service, instance, args, kwargs, context):
    span_type = "storage"
    span_subtype = "s3"
    span_action = operation_name
    if len(args) > 1 and "Bucket" in args[1]:
        bucket = args[1]["Bucket"]
    else:
        # TODO handle Access Points
        bucket = ""
    signature = f"S3 {operation_name} {bucket}"

    context["destination"]["name"] = span_subtype
    context["destination"]["resource"] = bucket
    context["destination"]["service"] = {"type": span_type}

    return HandlerInfo(signature, span_type, span_subtype, span_action, context)


def handle_dynamodb(operation_name, service, instance, args, kwargs, context):
    span_type = "db"
    span_subtype = "dynamodb"
    span_action = "query"
    if len(args) > 1 and "TableName" in args[1]:
        table = args[1]["TableName"]
    else:
        table = ""
    signature = f"DynamoDB {operation_name} {table}".rstrip()

    context["db"] = {"type": "dynamodb", "instance": instance.meta.region_name}
    if operation_name == "Query" and len(args) > 1 and "KeyConditionExpression" in args[1]:
        context["db"]["statement"] = args[1]["KeyConditionExpression"]

    context["destination"]["name"] = span_subtype
    context["destination"]["resource"] = table
    context["destination"]["service"] = {"type": span_type}
    return HandlerInfo(signature, span_type, span_subtype, span_action, context)


def handle_sns(operation_name, service, instance, args, kwargs, context):
    if operation_name != "Publish":
        # only "publish" is handled specifically, other endpoints get the default treatment
        return False
    span_type = "messaging"
    span_subtype = "sns"
    span_action = "send"
    topic_name = ""
    if len(args) > 1:
        if "Name" in args[1]:
            topic_name = args[1]["Name"]
        if "TopicArn" in args[1]:
            topic_name = args[1]["TopicArn"].rsplit(":", maxsplit=1)[-1]
    signature = f"SNS {operation_name} {topic_name}".rstrip()
    context["destination"]["name"] = span_subtype
    context["destination"]["resource"] = f"{span_subtype}/{topic_name}" if topic_name else span_subtype
    context["destination"]["type"] = span_type
    return HandlerInfo(signature, span_type, span_subtype, span_action, context)


def handle_sqs(operation_name, service, instance, args, kwargs, destination):
    pass


def handle_default(operation_name, service, instance, args, kwargs, destination):
    span_type = "aws"
    span_subtype = service.lower()
    span_action = operation_name

    signature = f"{service}:{operation_name}"
    return HandlerInfo(signature, span_type, span_subtype, span_action, destination)


handlers = {
    "S3": handle_s3,
    "DynamoDB": handle_dynamodb,
    "SNS": handle_sns,
    "default": handle_default,
}
