#  BSD 3-Clause License
#
#  Copyright (c) 2012, the Sentry Team, see AUTHORS for more details
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

import base64
import os
import re
from functools import partial

from elasticapm.conf import constants
from elasticapm.utils import compat, encoding

try:
    from functools import partialmethod

    partial_types = (partial, partialmethod)
except ImportError:
    # Python 2
    partial_types = (partial,)


default_ports = {"https": 443, "http": 80, "postgresql": 5432, "mysql": 3306, "mssql": 1433}


def varmap(func, var, context=None, name=None):
    """
    Executes ``func(key_name, value)`` on all values,
    recursively discovering dict and list scoped
    values.
    """
    if context is None:
        context = set()
    objid = id(var)
    if objid in context:
        return func(name, "<...>")
    context.add(objid)
    if isinstance(var, dict):
        ret = func(name, dict((k, varmap(func, v, context, k)) for k, v in compat.iteritems(var)))
    elif isinstance(var, (list, tuple)):
        ret = func(name, [varmap(func, f, context, name) for f in var])
    else:
        ret = func(name, var)
    context.remove(objid)
    return ret


def get_name_from_func(func):
    # partials don't have `__module__` or `__name__`, so we use the values from the "inner" function
    if isinstance(func, partial_types):
        return "partial({})".format(get_name_from_func(func.func))
    elif hasattr(func, "_partialmethod") and hasattr(func._partialmethod, "func"):
        return "partial({})".format(get_name_from_func(func._partialmethod.func))

    module = func.__module__

    if hasattr(func, "__name__"):
        view_name = func.__name__
    else:  # Fall back if there's no __name__
        view_name = func.__class__.__name__

    return "{0}.{1}".format(module, view_name)


def build_name_with_http_method_prefix(name, request):
    return " ".join((request.method, name)) if name else name


def is_master_process():
    # currently only recognizes uwsgi master process
    try:
        import uwsgi

        return os.getpid() == uwsgi.masterpid()
    except ImportError:
        return False


def get_url_dict(url):
    parse_result = compat.urlparse.urlparse(url)

    url_dict = {
        "full": encoding.keyword_field(url),
        "protocol": parse_result.scheme + ":",
        "hostname": encoding.keyword_field(parse_result.hostname),
        "pathname": encoding.keyword_field(parse_result.path),
    }

    port = None if parse_result.port is None else str(parse_result.port)

    if port:
        url_dict["port"] = port
    if parse_result.query:
        url_dict["search"] = encoding.keyword_field("?" + parse_result.query)
    return url_dict


def sanitize_url(url):
    if "@" not in url:
        return url
    parts = compat.urlparse.urlparse(url)
    return url.replace("%s:%s" % (parts.username, parts.password), "%s:%s" % (parts.username, constants.MASK))


def get_host_from_url(url):
    parsed_url = compat.urlparse.urlparse(url)
    host = parsed_url.hostname or " "

    if parsed_url.port and default_ports.get(parsed_url.scheme) != parsed_url.port:
        host += ":" + str(parsed_url.port)

    return host


def url_to_destination(url, service_type="external"):
    parts = compat.urlparse.urlsplit(url)
    hostname = parts.hostname
    # preserve brackets for IPv6 URLs
    if "://[" in url:
        hostname = "[%s]" % hostname
    port = parts.port
    default_port = default_ports.get(parts.scheme, None)
    name = "%s://%s" % (parts.scheme, hostname)
    resource = hostname
    if not port and parts.scheme in default_ports:
        port = default_ports[parts.scheme]
    if port:
        if port != default_port:
            name += ":%d" % port
        resource += ":%d" % port
    return {"service": {"name": name, "resource": resource, "type": service_type}}


def read_pem_file(file_obj):
    cert = b""
    for line in file_obj:
        if line.startswith(b"-----BEGIN CERTIFICATE-----"):
            break
    for line in file_obj:
        if not line.startswith(b"-----END CERTIFICATE-----"):
            cert += line.strip()
    return base64.b64decode(cert)


def starmatch_to_regex(pattern):
    i, n = 0, len(pattern)
    res = []
    while i < n:
        c = pattern[i]
        i = i + 1
        if c == "*":
            res.append(".*")
        else:
            res.append(re.escape(c))
    return re.compile(r"(?:%s)\Z" % "".join(res), re.IGNORECASE | re.DOTALL)
