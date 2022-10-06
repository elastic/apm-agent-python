# -*- coding: utf-8 -*-
#
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


import datetime
import itertools
import uuid
from decimal import Decimal

from elasticapm.conf.constants import KEYWORD_MAX_LENGTH, LABEL_RE, LABEL_TYPES, LONG_FIELD_MAX_LENGTH

PROTECTED_TYPES = (int, type(None), float, Decimal, datetime.datetime, datetime.date, datetime.time)


def is_protected_type(obj):
    """Determine if the object instance is of a protected type.

    Objects of protected types are preserved as-is when passed to
    force_text(strings_only=True).
    """
    return isinstance(obj, PROTECTED_TYPES)


def force_text(s, encoding="utf-8", strings_only=False, errors="strict"):
    """
    Similar to smart_text, except that lazy instances are resolved to
    strings, rather than kept as lazy objects.

    If strings_only is True, don't convert (some) non-string-like objects.
    """
    # Handle the common case first, saves 30-40% when s is an instance of
    # str. This function gets called often in that setting.
    #
    # Adapted from Django
    if isinstance(s, str):
        return s
    if strings_only and is_protected_type(s):
        return s
    try:
        if not isinstance(s, str):
            if hasattr(s, "__unicode__"):
                s = s.__unicode__()
            else:
                if isinstance(s, bytes):
                    s = str(s, encoding, errors)
                else:
                    s = str(s)
        else:
            # Note: We use .decode() here, instead of str(s, encoding,
            # errors), so that if s is a SafeBytes, it ends up being a
            # SafeText at the end.
            s = s.decode(encoding, errors)
    except UnicodeDecodeError as e:
        if not isinstance(s, Exception):
            raise UnicodeDecodeError(*e.args)
        else:
            # If we get to here, the caller has passed in an Exception
            # subclass populated with non-ASCII bytestring data without a
            # working unicode method. Try to handle this without raising a
            # further exception by individually forcing the exception args
            # to unicode.
            s = " ".join([force_text(arg, encoding, strings_only, errors) for arg in s])
    return s


def _has_elasticapm_metadata(value):
    try:
        return callable(value.__getattribute__("__elasticapm__"))
    except Exception:
        return False


def transform(value, stack=None, context=None):
    # TODO: make this extendable
    if context is None:
        context = {}
    if stack is None:
        stack = []

    objid = id(value)
    if objid in context:
        return "<...>"

    context[objid] = 1
    transform_rec = lambda o: transform(o, stack + [value], context)

    if any(value is s for s in stack):
        ret = "cycle"
    elif isinstance(value, (tuple, list, set, frozenset)):
        try:
            ret = type(value)(transform_rec(o) for o in value)
        except Exception:
            # We may be dealing with a namedtuple
            class value_type(list):
                __name__ = type(value).__name__

            ret = value_type(transform_rec(o) for o in value)
    elif isinstance(value, uuid.UUID):
        try:
            ret = repr(value)
        except AttributeError:
            ret = None
    elif isinstance(value, dict):
        ret = dict((to_unicode(k), transform_rec(v)) for k, v in value.items())
    elif isinstance(value, str):
        ret = to_unicode(value)
    elif isinstance(value, bytes):
        ret = to_string(value)
    elif not isinstance(value, type) and _has_elasticapm_metadata(value):
        ret = transform_rec(value.__elasticapm__())
    elif isinstance(value, bool):
        ret = bool(value)
    elif isinstance(value, float):
        ret = float(value)
    elif isinstance(value, int):
        ret = int(value)
    elif value is not None:
        try:
            ret = transform(repr(value))
        except Exception:
            # It's common case that a model's __unicode__ definition may try to query the database
            # which if it was not cleaned up correctly, would hit a transaction aborted exception
            ret = "<BadRepr: %s>" % type(value)
    else:
        ret = None
    del context[objid]
    return ret


def to_unicode(value):
    try:
        value = str(force_text(value))
    except (UnicodeEncodeError, UnicodeDecodeError):
        value = "(Error decoding value)"
    except Exception:  # in some cases we get a different exception
        try:
            value = bytes(repr(type(value)))
        except Exception:
            value = "(Error decoding value)"
    return value


def to_string(value):
    try:
        return bytes(value.decode("utf-8").encode("utf-8"))
    except Exception:
        return to_unicode(value).encode("utf-8")


def shorten(var, list_length=50, string_length=200, dict_length=50, **kwargs):
    """
    Shorten a given variable based on configurable maximum lengths, leaving
    breadcrumbs in the object to show that it was shortened.

    For strings, truncate the string to the max length, and append "..." so
    the user knows data was lost.

    For lists, truncate the list to the max length, and append two new strings
    to the list: "..." and "(<x> more elements)" where <x> is the number of
    elements removed.

    For dicts, truncate the dict to the max length (based on number of key/value
    pairs) and add a new (key, value) pair to the dict:
    ("...", "(<x> more elements)") where <x> is the number of key/value pairs
    removed.

    :param var: Variable to be shortened
    :param list_length: Max length (in items) of lists
    :param string_length: Max length (in characters) of strings
    :param dict_length: Max length (in key/value pairs) of dicts
    :return: Shortened variable
    """
    var = transform(var)
    if isinstance(var, str) and len(var) > string_length:
        var = var[: string_length - 3] + "..."
    elif isinstance(var, (list, tuple, set, frozenset)) and len(var) > list_length:
        # TODO: we should write a real API for storing some metadata with vars when
        # we get around to doing ref storage
        var = list(var)[:list_length] + ["...", "(%d more elements)" % (len(var) - list_length,)]
    elif isinstance(var, dict) and len(var) > dict_length:
        trimmed_tuples = [(k, v) for (k, v) in itertools.islice(var.items(), dict_length)]
        if "<truncated>" not in var:
            trimmed_tuples += [("<truncated>", "(%d more elements)" % (len(var) - dict_length))]
        var = dict(trimmed_tuples)
    return var


def keyword_field(string):
    """
    If the given string is longer than KEYWORD_MAX_LENGTH, truncate it to
    KEYWORD_MAX_LENGTH-1, adding the "…" character at the end.
    """
    if not isinstance(string, str) or len(string) <= KEYWORD_MAX_LENGTH:
        return string
    return string[: KEYWORD_MAX_LENGTH - 1] + "…"


def long_field(data):
    """
    If the given data, converted to string, is longer than LONG_FIELD_MAX_LENGTH,
    truncate it to LONG_FIELD_MAX_LENGTH-1, adding the "…" character at the end.

    If data is bytes, truncate it to LONG_FIELD_MAX_LENGTH-3, adding b"..." to
    the end.

    Returns the original data if truncation is not required.

    Per https://github.com/elastic/apm/blob/main/specs/agents/field-limits.md#long_field_max_length-configuration,
    this should only be applied to the following fields:

    - `transaction.context.request.body`, `error.context.request.body`
    - `transaction.context.message.body`, `span.context.message.body`, `error.context.message.body`
    - `span.context.db.statement`
    - `error.exception.message`
    - `error.log.message`

    Other fields should be truncated via `elasticapm.utils.encoding.keyword_field()`
    """
    str_or_bytes = str(data) if not isinstance(data, (str, bytes)) else data
    if len(str_or_bytes) > LONG_FIELD_MAX_LENGTH:
        if isinstance(str_or_bytes, bytes):
            return str_or_bytes[: LONG_FIELD_MAX_LENGTH - 3] + b"..."
        else:
            return str_or_bytes[: LONG_FIELD_MAX_LENGTH - 1] + "…"
    else:
        return data


def enforce_label_format(labels):
    """
    Enforces label format:
      * dots, double quotes or stars in keys are replaced by underscores
      * string values are limited to a length of 1024 characters
      * values can only be of a limited set of types

    :param labels: a dictionary of labels
    :return: a new dictionary with sanitized keys/values
    """
    new = {}
    for key, value in labels.items():
        if not isinstance(value, LABEL_TYPES):
            value = keyword_field(str(value))
        new[LABEL_RE.sub("_", str(key))] = value
    return new
