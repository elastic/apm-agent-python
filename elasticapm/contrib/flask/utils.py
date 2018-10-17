from werkzeug.exceptions import ClientDisconnected

from elasticapm.conf import constants
from elasticapm.utils import compat, get_url_dict
from elasticapm.utils.wsgi import get_environ, get_headers


def get_data_from_request(request, capture_body=False):
    result = {
        "env": dict(get_environ(request.environ)),
        "headers": dict(get_headers(request.environ)),
        "method": request.method,
        "socket": {"remote_address": request.environ.get("REMOTE_ADDR"), "encrypted": request.is_secure},
        "cookies": request.cookies,
    }
    if request.method in constants.HTTP_WITH_BODY:
        body = None
        if request.content_type == "application/x-www-form-urlencoded":
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
                body = request.get_data(as_text=True)
            except ClientDisconnected:
                pass

        if body is not None:
            result["body"] = body if capture_body else "[REDACTED]"

    result["url"] = get_url_dict(request.url)
    return result


def get_data_from_response(response):
    result = {}

    if isinstance(getattr(response, "status_code", None), compat.integer_types):
        result["status_code"] = response.status_code

    if getattr(response, "headers", None):
        headers = response.headers
        result["headers"] = {key: ";".join(headers.getlist(key)) for key in compat.iterkeys(headers)}
    return result
