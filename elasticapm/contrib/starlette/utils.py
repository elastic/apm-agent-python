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

from elasticapm.conf import constants
from elasticapm.utils import compat, get_url_dict
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import Message


async def get_data_from_request(request: Request, capture_body=False, capture_headers=True) -> dict:
    """Loads data from incoming request for APM capturing.

    Args:
        request (Request)
        capture_body (bool): Loads also request body if True
        capture_headers (bool): Loads also request headers if True

    Returns:
        dict
    """
    result = {
        "method": request.method,
        "socket": {"remote_address": _get_client_ip(request), "encrypted": request.url.is_secure},
        "cookies": request.cookies,
    }
    if capture_headers:
        result["headers"] = dict(request.headers)

    if request.method in constants.HTTP_WITH_BODY:
        body = None
        try:
            body = await get_body(request)
            if request.headers.get("content-type") == "application/x-www-form-urlencoded":
                body = await query_params_to_dict(body)
            else:
                body = json.loads(body)
        except Exception:
            pass
        if body is not None:
            result["body"] = body if capture_body else "[REDACTED]"

    result["url"] = get_url_dict(str(request.url))

    return result


async def get_data_from_response(response: Response, capture_body=False, capture_headers=True) -> dict:
    """Loads data from response for APM capturing.

    Args:
        response (Response)
        capture_body (bool): Loads also response body if True
        capture_headers (bool): Loads also response HTTP headers if True

    Returns:
        dict
    """
    result = {}

    if isinstance(getattr(response, "status_code", None), compat.integer_types):
        result["status_code"] = response.status_code

    if capture_headers and getattr(response, "headers", None):
        headers = response.headers
        result["headers"] = {key: ";".join(headers.getlist(key)) for key in compat.iterkeys(headers)}

    if capture_body:
        result["body"] = response.body.decode("utf-8")

    return result


async def set_body(request: Request, body: bytes):
    """Overwrites body in Starlette.

    Args:
        request (Request)
        body (bytes)
    """

    async def receive() -> Message:
        return {"type": "http.request", "body": body}

    request._receive = receive


async def get_body(request: Request) -> str:
    """Gets body from the request.

    todo: This is not very pretty however it is not usual to get request body out of the target method (business logic).

    Args:
        request (Request)

    Returns:
        str
    """
    body = await request.body()
    await set_body(request, body)

    request._stream_consumed = False

    return body.decode("utf-8")


async def query_params_to_dict(query_params: str) -> dict:
    """Transforms query params from URL to dictionary

    Args:
        query_params (str)

    Returns:
        dict

    Examples:
        >>> print(query_params_to_dict(b"key=val&key2=val2"))
        {"key": "val", "key2": "val2"}
    """
    query_params = query_params.split("&")
    res = {}
    for param in query_params:
        key, val = param.split("=")
        res[key] = val

    return res


def _get_client_ip(request: Request):
    x_forwarded_for = request.headers.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.headers.get("REMOTE_ADDR")
    return ip
