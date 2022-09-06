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

import urllib.parse
from collections import namedtuple

from elasticapm.conf import constants
from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.traces import SpanType, capture_span, execution_context
from elasticapm.utils.disttracing import TraceParent
from elasticapm.utils.logging import get_logger

logger = get_logger("elasticapm.instrument")

SQS_MAX_ATTRIBUTES = 10


HandlerInfo = namedtuple("HandlerInfo", ("signature", "span_type", "span_subtype", "span_action", "context"))

# Used for boto3 < 1.7
endpoint_to_service_id = {"SNS": "SNS", "S3": "S3", "DYNAMODB": "DynamoDB", "SQS": "SQS"}


class BotocoreInstrumentation(AbstractInstrumentedModule):
    name = "botocore"

    instrument_list = [("botocore.client", "BaseClient._make_api_call")]

    capture_span_ctx = capture_span

    def _call(self, service, instance, args, kwargs):
        """
        This is split out from `call()` so that it can be re-used by the
        aiobotocore instrumentation without duplicating all of this code.
        """
        operation_name = kwargs.get("operation_name", args[0])

        parsed_url = urllib.parse.urlparse(instance.meta.endpoint_url)
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

        return self.capture_span_ctx(
            handler_info.signature,
            span_type=handler_info.span_type,
            leaf=True,
            span_subtype=handler_info.span_subtype,
            span_action=handler_info.span_action,
            extra=handler_info.context,
        )

    def _get_service(self, instance):
        service_model = instance.meta.service_model
        if hasattr(service_model, "service_id"):  # added in boto3 1.7
            service = service_model.service_id
        else:
            service = service_model.service_name.upper()
            service = endpoint_to_service_id.get(service, service)
        return service

    def call(self, module, method, wrapped, instance, args, kwargs):
        service = self._get_service(instance)

        ctx = self._call(service, instance, args, kwargs)
        with ctx as span:
            if service in pre_span_modifiers:
                pre_span_modifiers[service](span, args, kwargs)
            result = wrapped(*args, **kwargs)
            if service in post_span_modifiers:
                post_span_modifiers[service](span, args, kwargs, result)
            request_id = result.get("ResponseMetadata", {}).get("RequestId")
            if request_id:
                span.update_context("http", {"request": {"id": request_id}})
            return result


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

    context["destination"]["service"] = {"name": span_subtype, "resource": bucket, "type": span_type}

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

    context["destination"]["service"] = {"name": span_subtype, "resource": table, "type": span_type}
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
    context["destination"]["service"] = {
        "name": span_subtype,
        "resource": f"{span_subtype}/{topic_name}" if topic_name else span_subtype,
        "type": span_type,
    }
    return HandlerInfo(signature, span_type, span_subtype, span_action, context)


SQS_OPERATIONS = {
    "SendMessage": {"span_action": "send", "signature": "SEND to"},
    "SendMessageBatch": {"span_action": "send_batch", "signature": "SEND_BATCH to"},
    "ReceiveMessage": {"span_action": "receive", "signature": "RECEIVE from"},
    "DeleteMessage": {"span_action": "delete", "signature": "DELETE from"},
    "DeleteMessageBatch": {"span_action": "delete_batch", "signature": "DELETE_BATCH from"},
}


def handle_sqs(operation_name, service, instance, args, kwargs, context):
    op = SQS_OPERATIONS.get(operation_name, None)
    if not op:
        # only "publish" is handled specifically, other endpoints get the default treatment
        return False
    span_type = "messaging"
    span_subtype = "sqs"
    topic_name = ""

    if len(args) > 1:
        topic_name = args[1]["QueueUrl"].rsplit("/", maxsplit=1)[-1]
    signature = f"SQS {op['signature']} {topic_name}".rstrip() if topic_name else f"SQS {op['signature']}"
    context["destination"]["service"] = {
        "name": span_subtype,
        "resource": f"{span_subtype}/{topic_name}" if topic_name else span_subtype,
        "type": span_type,
    }
    return HandlerInfo(signature, span_type, span_subtype, op["span_action"], context)


def modify_span_sqs_pre(span, args, kwargs):
    operation_name = kwargs.get("operation_name", args[0])
    if span.id:
        trace_parent = span.transaction.trace_parent.copy_from(span_id=span.id)
    else:
        # this is a dropped span, use transaction id instead
        transaction = execution_context.get_transaction()
        trace_parent = transaction.trace_parent.copy_from(span_id=transaction.id)
    attributes = {constants.TRACEPARENT_HEADER_NAME: {"DataType": "String", "StringValue": trace_parent.to_string()}}
    if trace_parent.tracestate:
        attributes[constants.TRACESTATE_HEADER_NAME] = {"DataType": "String", "StringValue": trace_parent.tracestate}
    if len(args) > 1:
        if operation_name in ("SendMessage", "SendMessageBatch"):
            attributes_count = len(attributes)
            if operation_name == "SendMessage":
                messages = [args[1]]
            else:
                messages = args[1]["Entries"]
            for message in messages:
                message["MessageAttributes"] = message.get("MessageAttributes") or {}
                if len(message["MessageAttributes"]) + attributes_count <= SQS_MAX_ATTRIBUTES:
                    message["MessageAttributes"].update(attributes)
                else:
                    logger.info("Not adding disttracing headers to message due to attribute limit reached")
        elif operation_name == "ReceiveMessage":
            message_attributes = args[1].setdefault("MessageAttributeNames", [])
            if "All" not in message_attributes:
                message_attributes.extend([constants.TRACEPARENT_HEADER_NAME, constants.TRACESTATE_HEADER_NAME])


def modify_span_sqs_post(span: SpanType, args, kwargs, result):
    operation_name = kwargs.get("operation_name", args[0])
    if operation_name == "ReceiveMessage" and "Messages" in result:
        for message in result["Messages"][:1000]:  # only up to 1000 span links are recorded
            if "MessageAttributes" in message and constants.TRACEPARENT_HEADER_NAME in message["MessageAttributes"]:
                tp = TraceParent.from_string(
                    message["MessageAttributes"][constants.TRACEPARENT_HEADER_NAME]["StringValue"]
                )
                span.add_link(tp)


def handle_default(operation_name, service, instance, args, kwargs, destination):
    span_type = "aws"
    span_subtype = service.lower()
    span_action = operation_name

    destination["service"] = {"name": span_subtype, "resource": span_subtype, "type": span_type}

    signature = f"{service}:{operation_name}"
    return HandlerInfo(signature, span_type, span_subtype, span_action, destination)


handlers = {
    "S3": handle_s3,
    "DynamoDB": handle_dynamodb,
    "SNS": handle_sns,
    "SQS": handle_sqs,
    "default": handle_default,
}

pre_span_modifiers = {
    "SQS": modify_span_sqs_pre,
}

post_span_modifiers = {
    "SQS": modify_span_sqs_post,
}
