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
from functools import partial

from elasticapm.utils import compat, encoding

try:
    from functools import partialmethod

    partial_types = (partial, partialmethod)
except ImportError:
    # Python 2
    partial_types = (partial,)


default_ports = {"https": 433, "http": 80, "postgresql": 5432}


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
        ret = dict((k, varmap(func, v, context, k)) for k, v in compat.iteritems(var))
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
    scheme, netloc, path, params, query, fragment = compat.urlparse.urlparse(url)
    if ":" in netloc:
        hostname, port = netloc.split(":")
    else:
        hostname, port = (netloc, None)
    url_dict = {
        "full": encoding.keyword_field(url),
        "protocol": scheme + ":",
        "hostname": encoding.keyword_field(hostname),
        "pathname": encoding.keyword_field(path),
    }
    if port:
        url_dict["port"] = port
    if query:
        url_dict["search"] = encoding.keyword_field("?" + query)
    return url_dict


def read_pem_file(file_obj):
    cert = b""
    for line in file_obj:
        if line.startswith(b"-----BEGIN CERTIFICATE-----"):
            break
    for line in file_obj:
        if not line.startswith(b"-----END CERTIFICATE-----"):
            cert += line.strip()
    return base64.b64decode(cert)
