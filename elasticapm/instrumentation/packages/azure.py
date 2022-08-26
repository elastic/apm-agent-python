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

import json
import urllib.parse
from collections import namedtuple

from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.traces import capture_span
from elasticapm.utils.logging import get_logger

logger = get_logger("elasticapm.instrument")

HandlerInfo = namedtuple("HandlerInfo", ("signature", "span_type", "span_subtype", "span_action", "context"))


class AzureInstrumentation(AbstractInstrumentedModule):
    name = "azure"

    instrument_list = [
        ("azure.core.pipeline._base", "Pipeline.run"),
        ("azure.cosmosdb.table.common._http.httpclient", "_HTTPClient.perform_request"),
    ]

    def call(self, module, method, wrapped, instance, args, kwargs):
        if len(args) == 1:
            request = args[0]
        else:
            request = kwargs["request"]

        if hasattr(request, "url"):  # Azure Storage HttpRequest
            parsed_url = urllib.parse.urlparse(request.url)
            hostname = parsed_url.hostname
            port = parsed_url.port
            path = parsed_url.path
            query_params = urllib.parse.parse_qs(parsed_url.query)
        else:  # CosmosDB HTTPRequest
            hostname = request.host
            port = hostname.split(":")[1] if ":" in hostname else 80
            path = request.path
            query_params = request.query

        # Detect the service
        service = None
        if ".blob.core." in hostname:
            service = "azureblob"
            service_type = "storage"
        elif ".queue.core." in hostname:
            service = "azurequeue"
            service_type = "messaging"
        elif ".table.core." in hostname:
            service = "azuretable"
            service_type = "storage"
        elif ".file.core." in hostname:
            service = "azurefile"
            service_type = "storage"

        # Do not create a span if we don't recognize the service
        if not service:
            return wrapped(*args, **kwargs)

        context = {
            "destination": {
                "address": hostname,
                "port": port,
            }
        }

        handler_info = handlers[service](request, hostname, path, query_params, service, service_type, context)

        with capture_span(
            handler_info.signature,
            span_type=handler_info.span_type,
            leaf=True,
            span_subtype=handler_info.span_subtype,
            span_action=handler_info.span_action,
            extra=handler_info.context,
        ):
            return wrapped(*args, **kwargs)


def handle_azureblob(request, hostname, path, query_params, service, service_type, context):
    """
    Returns the HandlerInfo for Azure Blob Storage operations
    """
    account_name = hostname.split(".")[0]
    context["destination"]["service"] = {
        "name": service,
        "resource": "{}/{}".format(service, account_name),
        "type": service_type,
    }
    method = request.method
    headers = request.headers
    blob = path[1:]

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
            # https://github.com/elastic/apm/blob/main/specs/agents/tracing-instrumentation-azure.md
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


def handle_azurequeue(request, hostname, path, query_params, service, service_type, context):
    """
    Returns the HandlerInfo for Azure Queue operations
    """
    account_name = hostname.split(".")[0]
    method = request.method
    resource_name = path.split("/")[1] if "/" in path else account_name  # /queuename/messages
    context["destination"]["service"] = {
        "name": service,
        "resource": "{}/{}".format(service, resource_name),
        "type": service_type,
    }

    operation_name = "UNKNOWN"
    preposition = "to "
    if method.lower() == "delete":
        operation_name = "DELETE"
        preposition = ""
        if path.endswith("/messages") and "popreceipt" not in query_params:
            operation_name = "CLEAR"
        elif query_params.get("popreceipt", []):
            # Redundant, but included in case the table at
            # https://github.com/elastic/apm/blob/main/specs/agents/tracing-instrumentation-azure.md
            # changes in the future
            operation_name = "DELETE"
            preposition = "from "
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
    elif method.lower() == "head":
        operation_name = "RECEIVE"
        preposition = "from "
        if "metadata" in query_params.get("comp", []):
            operation_name = "GETMETADATA"
        elif "acl" in query_params.get("comp", []):
            operation_name = "GETACL"
    elif method.lower() == "options":
        operation_name = "PREFLIGHT"
        preposition = "from "
    elif method.lower() == "post":
        operation_name = "SEND"
        preposition = "to "
    elif method.lower() == "put":
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
    signature = "AzureQueue {} {}{}".format(operation_name, preposition, resource_name)

    return HandlerInfo(signature, service_type, service, operation_name.lower(), context)


def handle_azuretable(request, hostname, path, query_params, service, service_type, context):
    """
    Returns the HandlerInfo for Azure Table Storage operations
    """
    account_name = hostname.split(".")[0]
    method = request.method
    body = request.body
    try:
        body = json.loads(body)
    except json.decoder.JSONDecodeError:  # str not bytes
        body = {}
    # /tablename(PartitionKey='<partition-key>',RowKey='<row-key>')
    resource_name = path.split("/", 1)[1] if "/" in path else path
    context["destination"]["service"] = {
        "name": service,
        "resource": "{}/{}".format(service, account_name),
        "type": service_type,
    }

    operation_name = "Unknown"
    if method.lower() == "put":
        operation_name = "Update"
        if "properties" in query_params.get("comp", []):
            operation_name = "SetProperties"
        elif "acl" in query_params.get("comp", []):
            operation_name = "SetAcl"
    elif method.lower() == "post":
        if resource_name == "Tables":
            resource_name = body.get("TableName", resource_name)
            operation_name = "Create"
        else:  # /<tablename>
            operation_name = "Insert"
    elif method.lower() == "get":
        operation_name = "Query"  # for both /Tables and /table()
        if "properties" in query_params.get("comp", []):
            operation_name = "GetProperties"
        elif "stats" in query_params.get("comp", []):
            operation_name = "Stats"
        elif "acl" in query_params.get("comp", []):
            operation_name = "GetAcl"
    elif method.lower() == "delete":
        operation_name = "Delete"
        if "Tables" in resource_name and "'" in resource_name:
            resource_name = resource_name.split("'")[1]  # /Tables('<table_name>')
    elif method.lower() == "options":
        operation_name = "Preflight"
    elif method.lower() == "head" and "acl" in query_params.get("comp", []):
        operation_name = "GetAcl"
    elif method.lower() == "merge":
        operation_name = "Merge"

    signature = "AzureTable {} {}".format(operation_name, resource_name)

    return HandlerInfo(signature, service_type, service, operation_name, context)


def handle_azurefile(request, hostname, path, query_params, service, service_type, context):
    """
    Returns the HandlerInfo for Azure File Share Storage operations
    """
    account_name = hostname.split(".")[0]
    method = request.method
    resource_name = path.split("/", 1)[1] if "/" in path else account_name
    headers = request.headers
    context["destination"]["service"] = {
        "name": service,
        "resource": "{}/{}".format(service, account_name),
        "type": service_type,
    }

    operation_name = "Unknown"
    if method.lower() == "get":
        operation_name = "Download"
        if "list" in query_params.get("comp", []):
            operation_name = "List"
        elif "properties" in query_params.get("comp", []):
            operation_name = "GetProperties"
        elif "share" in query_params.get("restype", []):
            operation_name = "GetProperties"
        elif "metadata" in query_params.get("comp", []):
            operation_name = "GetMetadata"
        elif "acl" in query_params.get("comp", []):
            operation_name = "GetAcl"
        elif "stats" in query_params.get("comp", []):
            operation_name = "Stats"
        elif "filepermission" in query_params.get("comp", []):
            operation_name = "GetPermission"
        elif "listhandles" in query_params.get("comp", []):
            operation_name = "ListHandles"
        elif "rangelist" in query_params.get("comp", []):
            operation_name = "ListRanges"
    elif method.lower() == "put":
        operation_name = "Create"
        if "properties" in query_params.get("comp", []):
            operation_name = "SetProperties"
            if "share" in query_params.get("restype", []):
                operation_name = "SetProperties"
        elif "snapshot" in query_params.get("comp", []):
            operation_name = "Snapshot"
        elif "metadata" in query_params.get("comp", []):
            operation_name = "SetMetadata"
        elif "undelete" in query_params.get("comp", []):
            operation_name = "Undelete"
        elif "acl" in query_params.get("comp", []):
            operation_name = "SetAcl"
        elif "filepermission" in query_params.get("comp", []):
            operation_name = "SetPermission"
        elif "directory" in query_params.get("restype", []):
            operation_name = "Create"
        elif "forceclosehandles" in query_params.get("comp", []):
            operation_name = "CloseHandles"
        elif "range" in query_params.get("comp", []):
            operation_name = "Upload"
        elif "x-ms-copy-source" in headers:
            operation_name = "Copy"
        elif "x-ms-copy-action" in headers and headers["x-ms-copy-action"] == "abort":
            operation_name = "Abort"
        elif "lease" in query_params.get("comp", []):
            operation_name = "Lease"
    elif method.lower() == "options":
        operation_name = "Preflight"
    elif method.lower() == "head":
        operation_name = "GetProperties"
        if "share" in query_params.get("restype", []):
            operation_name = "GetProperties"
        elif "metadata" in query_params.get("comp", []):
            operation_name = "GetMetadata"
        elif "acl" in query_params.get("comp", []):
            operation_name = "GetAcl"
    elif method.lower() == "delete":
        operation_name = "Delete"

    signature = "AzureFile {} {}".format(operation_name, resource_name)

    return HandlerInfo(signature, service_type, service, operation_name, context)


handlers = {
    "azureblob": handle_azureblob,
    "azurequeue": handle_azurequeue,
    "azuretable": handle_azuretable,
    "azurefile": handle_azurefile,
}
