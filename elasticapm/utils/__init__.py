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
import urllib.parse
from functools import partial
from types import FunctionType
from typing import Pattern

from elasticapm.conf import constants
from elasticapm.utils import encoding

try:
    from functools import partialmethod

    partial_types = (partial, partialmethod)
except ImportError:
    # Python 2
    partial_types = (partial,)


default_ports = {"https": 443, "http": 80, "postgresql": 5432, "mysql": 3306, "mssql": 1433}


def varmap(func, var, context=None, name=None, **kwargs):
    """
    Executes ``func(key_name, value)`` on all values,
    recursively discovering dict and list scoped
    values.
    """
    if context is None:
        context = set()
    objid = id(var)
    if objid in context:
        return func(name, "<...>", **kwargs)
    context.add(objid)

    # Apply func() before recursion, so that `shorten()` doesn't have to iterate over all the trimmed values
    ret = func(name, var, **kwargs)
    if isinstance(ret, dict):
        # iterate over a copy of the dictionary to avoid "dictionary changed size during iteration" issues
        ret = dict((k, varmap(func, v, context, k, **kwargs)) for k, v in ret.copy().items())
    elif isinstance(ret, (list, tuple)):
        # Apply func() before recursion, so that `shorten()` doesn't have to iterate over all the trimmed values
        ret = [varmap(func, f, context, name, **kwargs) for f in ret]
    context.remove(objid)
    return ret


def get_name_from_func(func: FunctionType) -> str:
    # partials don't have `__module__` or `__name__`, so we use the values from the "inner" function
    if isinstance(func, partial_types):
        return "partial({})".format(get_name_from_func(func.func))
    elif hasattr(func, "_partialmethod") and hasattr(func._partialmethod, "func"):
        return "partial({})".format(get_name_from_func(func._partialmethod.func))

    module = func.__module__

    if hasattr(func, "view_class"):
        view_name = func.view_class.__name__
    elif hasattr(func, "__name__"):
        view_name = func.__name__
    else:  # Fall back if there's no __name__
        view_name = func.__class__.__name__

    return "{0}.{1}".format(module, view_name)


def build_name_with_http_method_prefix(name, request):
    return " ".join((request.method, name)) if name else name


def is_master_process() -> bool:
    # currently only recognizes uwsgi master process
    try:
        import uwsgi

        return os.getpid() == uwsgi.masterpid()
    except ImportError:
        return False


def get_url_dict(url: str) -> dict:
    parse_result = urllib.parse.urlparse(url)

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


def sanitize_url(url: str) -> str:
    if "@" not in url:
        return url
    parts = urllib.parse.urlparse(url)
    return url.replace("%s:%s" % (parts.username, parts.password), "%s:%s" % (parts.username, constants.MASK))


def get_host_from_url(url: str) -> str:
    parsed_url = urllib.parse.urlparse(url)
    host = parsed_url.hostname or " "

    if parsed_url.port and default_ports.get(parsed_url.scheme) != parsed_url.port:
        host += ":" + str(parsed_url.port)

    return host


def url_to_destination_resource(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    hostname = parts.hostname if parts.hostname else ""
    # preserve brackets for IPv6 URLs
    if "://[" in url:
        hostname = "[%s]" % hostname
    try:
        port = parts.port
    except ValueError:
        # Malformed port, just use None rather than raising an exception
        port = None
    default_port = default_ports.get(parts.scheme, None)
    name = "%s://%s" % (parts.scheme, hostname)
    resource = hostname
    if not port and parts.scheme in default_ports:
        port = default_ports[parts.scheme]
    if port:
        if port != default_port:
            name += ":%d" % port
        resource += ":%d" % port
    return resource


def read_pem_file(file_obj) -> bytes:
    cert = b""
    for line in file_obj:
        if line.startswith(b"-----BEGIN CERTIFICATE-----"):
            break
    # scan until we find the first END CERTIFICATE marker
    for line in file_obj:
        if line.startswith(b"-----END CERTIFICATE-----"):
            break
        cert += line.strip()
    return base64.b64decode(cert)


def starmatch_to_regex(pattern: str) -> Pattern:
    options = re.DOTALL
    # check if we are case-sensitive
    if pattern.startswith("(?-i)"):
        pattern = pattern[5:]
    else:
        options |= re.IGNORECASE
    i, n = 0, len(pattern)
    res = []
    while i < n:
        c = pattern[i]
        i = i + 1
        if c == "*":
            res.append(".*")
        else:
            res.append(re.escape(c))
    return re.compile(r"(?:%s)\Z" % "".join(res), options)


def nested_key(d: dict, *args):
    """
    Traverses a dictionary for nested keys. Returns `None` if the at any point
    in the traversal a key cannot be found.

    Example:

        >>> from elasticapm.utils import nested_key
        >>> d = {"a": {"b": {"c": 0}}}
        >>> nested_key(d, "a", "b", "c")
        0
        >>> nested_key(d, "a", "b", "d")
        None
    """
    for arg in args:
        try:
            d = d[arg]
        except (TypeError, KeyError):
            d = None
            break
    return d
