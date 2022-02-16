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


from werkzeug.exceptions import ClientDisconnected

from elasticapm.conf import constants
from elasticapm.utils import compat, get_url_dict
from elasticapm.utils.wsgi import get_environ, get_headers


def get_data_from_request(request, config, event_type):
    result = {
        "env": dict(get_environ(request.environ)),
        "method": request.method,
        "socket": {"remote_address": request.environ.get("REMOTE_ADDR")},
        "cookies": request.cookies,
    }
    if config.capture_headers:
        result["headers"] = dict(get_headers(request.environ))
    if request.method in constants.HTTP_WITH_BODY:
        if config.capture_body not in ("all", event_type):
            result["body"] = "[REDACTED]"
        else:
            body = None
            if request.content_type == "application/x-www-form-urlencoded":
                body = compat.multidict_to_dict(request.form)
            elif request.content_type and request.content_type.startswith("multipart/form-data"):
                body = compat.multidict_to_dict(request.form)
                if request.files:
                    body["_files"] = {
                        field: val[0].filename if len(val) == 1 else [f.filename for f in val]
                        for field, val in request.files.lists()
                    }
            else:
                try:
                    body = request.get_data(as_text=True)
                except ClientDisconnected:
                    pass

            if body is not None:
                result["body"] = body

    result["url"] = get_url_dict(request.url)
    return result


def get_data_from_response(response, config, event_type):
    result = {}

    if isinstance(getattr(response, "status_code", None), int):
        result["status_code"] = response.status_code

    if config.capture_headers and getattr(response, "headers", None):
        headers = response.headers
        result["headers"] = {key: ";".join(headers.getlist(key)) for key in headers.keys()}
    return result
