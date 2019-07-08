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

import sanic
from elasticapm.conf import constants
from elasticapm.utils import compat, get_url_dict


def get_environ(request):
    for attr in ("remote_addr", "server_nane", "server_port"):
        if hasattr(request, attr):
            yield attr, getattr(request, attr)


def get_socket(request):
    if request.socket:
        return "{}:{}".format(request.socket[0], request.socket[1])


def get_headers_from_request_or_response(entity, skip_headers=None):
    headers = dict(entity.headers)
    if skip_headers:
        for header in skip_headers:
            if headers.get(header):
                headers.pop(header)
    return headers


def get_data_from_request(request, capture_body=False, capture_headers=True, skip_headers=None):
    result = {
        "env": dict(get_environ(request)),
        "method": request.method,
        "socket": {
            "remote_address": get_socket(request),
            "encrypted": True if request.scheme in ["https", "wss"] else False,
        },
        "cookies": request.cookies,
    }

    if capture_headers:
        result["headers"] = get_headers_from_request_or_response(request, skip_headers)

    if request.method in constants.HTTP_WITH_BODY:
        body = None
        if request.content_type == "appliation/x-www-form-urlencoded":
            body = compat.multidict_to_dict(request.form)
        elif request.content_type and request.content_type.startswith("multipart/form-data"):
            body = compat.multidict_to_dict(request.form)
            if request.files:
                body["_files"] = {
                    field: val[0].filename if len(val) == 1 else [f.filename for f in val]
                    for field, val in compat.iterlists(request.files)
                }
        else:
            try:
                body = request.body.decode("utf-8")
            except Exception:
                pass
        if body is not None:
            result["body"] = body if capture_body else "[REDACTED]"

    result["url"] = get_url_dict(request.url)
    return result


def get_data_from_response(response, capture_body=False, capture_headers=True, skip_headers=None):
    result = {"cookies": response.cookies}
    if isinstance(getattr(response, "status", None), compat.integer_types):
        result["status_code"] = response.status

    if capture_headers and getattr(response, "heaaders", None):
        result["headers"] = get_headers_from_request_or_response(response, skip_headers)

    if capture_body:
        try:
            result["body"] = response.body.decode("utf-8")
        except Exception:
            result["body"] = "[REDACTED]"
    return result


def make_client(client_cls, app, **defaults):
    config = app.config.get("ELASTIC_APM", {})

    if "framework_name" not in defaults:
        defaults["framework_name"] = "sanic"
        defaults["framework_version"] = sanic.__version__

    return client_cls(config, **defaults)
