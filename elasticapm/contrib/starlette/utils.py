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
import asyncio

from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.types import Message

from elasticapm.conf import Config, constants
from elasticapm.utils import compat, get_url_dict


async def get_data_from_request(request: Request, config: Config, event_type: str) -> dict:
    """Loads data from incoming request for APM capturing.

    Args:
        request (Request)
        config (Config)
        event_type (str)

    Returns:
        dict
    """
    result = {
        "method": request.method,
        "socket": {"remote_address": _get_client_ip(request), "encrypted": request.url.is_secure},
        "cookies": request.cookies,
    }
    if config.capture_headers:
        result["headers"] = dict(request.headers)

    if request.method in constants.HTTP_WITH_BODY:
        if config.capture_body not in ("all", event_type):
            result["body"] = "[REDACTED]"
        else:
            body = None
            try:
                body = await get_body(request)
            except Exception:
                pass
            if body is not None:
                result["body"] = body

    result["url"] = get_url_dict(str(request.url))

    return result


async def get_data_from_response(message: dict, config: Config, event_type: str) -> dict:
    """Loads data from response for APM capturing.

    Args:
        message (dict)
        config (Config)
        event_type (str)

    Returns:
        dict
    """
    result = {}

    if "status_code" in message:
        result["status_code"] = message["status"]

    if config.capture_headers and "headers" in message:
        headers = Headers(raw=message["headers"])
        result["headers"] = {key: ";".join(headers.getlist(key)) for key in compat.iterkeys(headers)}

    return result


async def set_body(request: Request, body: bytes):
    """Overwrites body in Starlette.

    Args:
        request (Request)
        body (bytes)
    """

    async def receive() -> Message:
        await asyncio.sleep(0)
        return {"type": "http.request", "body": body}

    request._receive = receive


async def get_body(request: Request) -> str:
    """Gets body from the request.

    When we consume the body, we replace the streaming mechanism with
    a mocked version -- this workaround came from
    https://github.com/encode/starlette/issues/495#issuecomment-513138055

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
