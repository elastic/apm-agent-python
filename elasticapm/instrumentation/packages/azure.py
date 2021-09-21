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
from elasticapm.utils.logging import get_logger

logger = get_logger("elasticapm.instrument")

HandlerInfo = namedtuple("HandlerInfo", ("signature", "span_type", "span_subtype", "span_action", "context"))


class AzureInstrumentation(AbstractInstrumentedModule):
    name = "azure"

    instrument_list = [("azure.core.pipeline._base", "Pipeline.run")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        if len(args) == 1:
            request = args[0]
        else:
            request = kwargs["request"]

        parsed_url = urlparse.urlparse(request.url)

        # Detect the service
        service = None
        if ".blob.core." in parsed_url.hostname:
            service = "azureblob"
            service_type = "storage"
        if ".queue.core." in parsed_url.hostname:
            service = "azurequeue"
            service_type = "messaging"

        # TODO this will probably not stay in the final instrumentation, just useful for detecting test errors
        if not service:
            raise NotImplementedError("service at hostname {} not implemented".format(parsed_url.hostname))

        context = {
            "destination": {
                "address": parsed_url.hostname,
                "port": parsed_url.port,
            }
        }

        handler_info = handlers[service](request, parsed_url, service, service_type, context)

        with capture_span(
            handler_info.signature,
            span_type=handler_info.span_type,
            leaf=True,
            span_subtype=handler_info.span_subtype,
            span_action=handler_info.span_action,
            extra=handler_info.context,
        ):
            return wrapped(*args, **kwargs)


def handle_azureblob(request, parsed_url, service, service_type, context):
    """
    Returns the HandlerInfo for Azure Blob Storage operations
    """
    account_name = parsed_url.hostname.split(".")[0]
    context["destination"]["service"] = {
        "name": service,
        "resource": "{}/{}".format(service, account_name),
        "type": service_type,
    }
    method = request.method
    headers = request.headers
    query_params = urlparse.parse_qs(parsed_url.query)
    blob = parsed_url.path[1:]

    operation_name = "Unknown"
    if method.lower() == "delete":
        operation_name = "Delete"
    elif method.lower() == "get":
        operation_name = "Download"
        if "container" in query_params.get("restype", []):
            operation_name = "GetProperties"
            if "acl" in query_params.get("comp", []):
                operation_name = "GetAcl"
            elif "list" in query_params.get("comp", []):
                operation_name = "ListBlobs"
        elif "metadata" in query_params.get("comp", []):
            operation_name = "GetMetadata"
        elif "list" in query_params.get("comp", []):
            operation_name = "ListContainers"
        elif "tags" in query_params.get("comp", []):
            operation_name = "GetTags"
            if query_params.get("where"):
                operation_name = "FindTags"
        elif "blocklist" in query_params.get("comp", []):
            operation_name = "GetBlockList"
        elif "pagelist" in query_params.get("comp", []):
            operation_name = "GetPageRanges"
        elif "stats" in query_params.get("comp", []):
            operation_name = "Stats"
        elif "blobs" in query_params.get("comp", []):
            operation_name = "FilterBlobs"
    elif method.lower() == "head":
        operation_name = "GetProperties"
        if "container" in query_params.get("restype", []) and query_params.get("comp") == "metadata":
            operation_name = "GetMetadata"
        elif "container" in query_params.get("restype", []) and query_params.get("comp") == "acl":
            operation_name = "GetAcl"
    elif method.lower() == "post":
        if "batch" in query_params.get("comp", []):
            operation_name = "Batch"
        elif "query" in query_params.get("comp", []):
            operation_name = "Query"
        elif "userdelegationkey" in query_params.get("comp", []):
            operation_name = "GetUserDelegationKey"
    elif method.lower() == "put":
        operation_name = "Create"
        if "x-ms-copy-source" in headers:
            operation_name = "Copy"
            # These are repetitive and unnecessary, but included in case the table at
            # https://github.com/elastic/apm/blob/master/specs/agents/tracing-instrumentation-azure.md
            # changes in the future
            if "block" in query_params.get("comp", []):
                operation_name = "Copy"
            elif "page" in query_params.get("comp", []):
                operation_name = "Copy"
            elif "incrementalcopy" in query_params.get("comp", []):
                operation_name = "Copy"
            elif "appendblock" in query_params.get("comp", []):
                operation_name = "Copy"
        elif "x-ms-blob-type" in headers:
            operation_name = "Upload"
        elif "x-ms-page-write" in headers and query_params.get("comp") == "page":
            operation_name = "Clear"
        elif "copy" in query_params.get("comp", []):
            operation_name = "Abort"
        elif "block" in query_params.get("comp", []):
            operation_name = "Upload"
        elif "blocklist" in query_params.get("comp", []):
            operation_name = "Upload"
        elif "page" in query_params.get("comp", []):
            operation_name = "Upload"
        elif "appendblock" in query_params.get("comp", []):
            operation_name = "Upload"
        elif "metadata" in query_params.get("comp", []):
            operation_name = "SetMetadata"
        elif "container" in query_params.get("restype", []) and query_params.get("comp") == "acl":
            operation_name = "SetAcl"
        elif "properties" in query_params.get("comp", []):
            operation_name = "SetProperties"
        elif "lease" in query_params.get("comp", []):
            operation_name = "Lease"
        elif "snapshot" in query_params.get("comp", []):
            operation_name = "Snapshot"
        elif "undelete" in query_params.get("comp", []):
            operation_name = "Undelete"
        elif "tags" in query_params.get("comp", []):
            operation_name = "SetTags"
        elif "tier" in query_params.get("comp", []):
            operation_name = "SetTier"
        elif "expiry" in query_params.get("comp", []):
            operation_name = "SetExpiry"
        elif "seal" in query_params.get("comp", []):
            operation_name = "Seal"
        elif "rename" in query_params.get("comp", []):
            operation_name = "Rename"

    signature = "AzureBlob {} {}".format(operation_name, blob)

    return HandlerInfo(signature, service_type, service, operation_name, context)


def handle_azurequeue(request, parsed_url, service, service_type, context):
    """
    Returns the HandlerInfo for Azure Blob Storage operations
    """
    account_name = parsed_url.hostname.split(".")[0]
    method = request.method
    query_params = urlparse.parse_qs(parsed_url.query)
    target_name = parsed_url.path.split("/")[1] if "/" in parsed_url.path else account_name  # /queuename/message
    context["destination"]["service"] = {
        "name": service,
        "resource": "{}/{}".format(service, target_name),
        "type": service_type,
    }

    operation_name = "Unknown"
    preposition = "to "
    if method.lower() == "delete":
        operation_name = "DELETE"
        preposition = ""
        if parsed_url.path.endswith("/messages"):
            operation_name = "CLEAR"
        elif query_params.get("popreceipt", []):
            # Redundant, but included in case the table at
            # https://github.com/elastic/apm/blob/master/specs/agents/tracing-instrumentation-azure.md
            # changes in the future
            operation_name = "DELETE"
    elif method.lower() == "get":
        operation_name = "RECEIVE"
        preposition = "from "
        if "list" in query_params.get("comp", []):
            operation_name = "LISTQUEUES"
        elif "properties" in query_params.get("comp", []):
            operation_name = "GETPROPERTIES"
        elif "stats" in query_params.get("comp", []):
            operation_name = "STATS"
        elif "metadata" in query_params.get("comp", []):
            operation_name = "GETMETADATA"
        elif "acl" in query_params.get("comp", []):
            operation_name = "GETACL"
        elif "true" in query_params.get("peekonly", []):
            operation_name = "PEEK"
    elif method.lower() == "HEAD":
        operation_name = "RECEIVE"
        preposition = "from "
        if "metadata" in query_params.get("comp", []):
            operation_name = "GETMETADATA"
        elif "acl" in query_params.get("comp", []):
            operation_name = "GETACL"
    elif method.lower() == "OPTIONS":
        operation_name = "PREFLIGHT"
        preposition = "from "
    elif method.lower() == "POST":
        operation_name = "SEND"
        preposition = "to "
    elif method.lower() == "PUT":
        operation_name = "CREATE"
        preposition = ""
        if "metadata" in query_params.get("comp", []):
            operation_name = "SETMETADATA"
            preposition = "for "
        elif "acl" in query_params.get("comp", []):
            operation_name = "SETACL"
            preposition = "for "
        elif "properties" in query_params.get("comp", []):
            operation_name = "SETPROPERTIES"
            preposition = "for "
        elif query_params.get("popreceipt", []):
            operation_name = "UPDATE"
            preposition = ""

    # If `preposition` is included, it should have a trailing space
    signature = "AzureQueue {} {}{}".format(operation_name, preposition, target_name)

    return HandlerInfo(signature, service_type, service, operation_name.lower(), context)


def handle_default():
    raise NotImplementedError()


handlers = {
    "azureblob": handle_azureblob,
    "azurequeue": handle_azurequeue,
    "default": handle_default,
}
