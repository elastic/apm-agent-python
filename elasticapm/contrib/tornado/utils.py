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
import elasticapm
from elasticapm.conf import constants

try:
    import tornado.escape
except ImportError:
    pass


def get_data_from_request(request, capture_body=False, capture_headers=True):
    """
    Capture relevant data from a tornado.httputil.HTTPServerRequest
    """
    result = {
        "method": request.method,
        "socket": {"remote_address": request.remote_ip, "encrypted": request.protocol == "https"},
        "cookies": request.cookies,
        "http_version": request.version,
    }
    if capture_headers:
        result["headers"] = dict(request.headers)
    if request.method in constants.HTTP_WITH_BODY:
        body = None
        try:
            # TODO what if request.body is a future?
            # https://github.com/tornadoweb/tornado/blob/18d7026853900c56a1879141235c6b6bd51b0a6a/tornado/web.py#L1691-L1699
            body = tornado.escape.json_decode(request.body)
        except Exception:
            pass

        if body is not None:
            result["body"] = body if capture_body else "[REDACTED]"

    result["url"] = elasticapm.utils.get_url_dict(request.full_url())
    return result


def get_data_from_response(request_handler, capture_headers=True):
    result = {}

    result["status_code"] = request_handler.get_status()

    if capture_headers:
        # TODO
        pass
    return result
