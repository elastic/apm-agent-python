"""
opbeat.utils.encoding
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

import uuid

from opbeat.utils import six


def is_protected_type(obj):
    """Determine if the object instance is of a protected type.

    Objects of protected types are preserved as-is when passed to
    force_text(strings_only=True).
    """
    from decimal import Decimal
    import datetime
    return isinstance(obj, six.integer_types + (type(None), float, Decimal,
        datetime.datetime, datetime.date, datetime.time))


def force_text(s, encoding='utf-8', strings_only=False, errors='strict'):
    """
    Similar to smart_text, except that lazy instances are resolved to
    strings, rather than kept as lazy objects.

    If strings_only is True, don't convert (some) non-string-like objects.
    """
    # Handle the common case first, saves 30-40% when s is an instance of
    # six.text_type. This function gets called often in that setting.
    #
    # Adapted from Django
    if isinstance(s, six.text_type):
        return s
    if strings_only and is_protected_type(s):
        return s
    try:
        if not isinstance(s, six.string_types):
            if hasattr(s, '__unicode__'):
                s = s.__unicode__()
            else:
                if six.PY3:
                    if isinstance(s, bytes):
                        s = six.text_type(s, encoding, errors)
                    else:
                        s = six.text_type(s)
                else:
                    s = six.text_type(bytes(s), encoding, errors)
        else:
            # Note: We use .decode() here, instead of six.text_type(s, encoding,
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
            s = ' '.join([force_text(arg, encoding, strings_only,
                    errors) for arg in s])
    return s


def _has_opbeat_metadata(value):
    try:
        return callable(value.__getattribute__("__opbeat__"))
    except:
        return False


def transform(value, stack=None, context=None):
    # TODO: make this extendable
    if context is None:
        context = {}
    if stack is None:
        stack = []

    objid = id(value)
    if objid in context:
        return '<...>'

    context[objid] = 1
    transform_rec = lambda o: transform(o, stack + [value], context)

    if any(value is s for s in stack):
        ret = 'cycle'
    elif isinstance(value, (tuple, list, set, frozenset)):
        try:
            ret = type(value)(transform_rec(o) for o in value)
        except Exception:
            # We may be dealing with a namedtuple
            class value_type(list):
                __name__ = type(value).__name__
            ret = value_type(transform_rec(o) for o in value)
    elif isinstance(value, uuid.UUID):
        ret = repr(value)
    elif isinstance(value, dict):
        ret = dict((to_unicode(k), transform_rec(v)) for k, v in six.iteritems(value))
    elif isinstance(value, six.text_type):
        ret = to_unicode(value)
    elif isinstance(value, six.binary_type):
        ret = to_string(value)
    elif not isinstance(value, six.class_types) and \
            _has_opbeat_metadata(value):
        ret = transform_rec(value.__opbeat__())
    elif isinstance(value, bool):
        ret = bool(value)
    elif isinstance(value, float):
        ret = float(value)
    elif isinstance(value, int):
        ret = int(value)
    elif six.PY2 and isinstance(value, long):
        ret = long(value)
    elif value is not None:
        try:
            ret = transform(repr(value))
        except:
            # It's common case that a model's __unicode__ definition may try to query the database
            # which if it was not cleaned up correctly, would hit a transaction aborted exception
            ret = u'<BadRepr: %s>' % type(value)
    else:
        ret = None
    del context[objid]
    return ret


def to_unicode(value):
    try:
        value = six.text_type(force_text(value))
    except (UnicodeEncodeError, UnicodeDecodeError):
        value = '(Error decoding value)'
    except Exception:  # in some cases we get a different exception
        try:
            value = six.binary_type(repr(type(value)))
        except Exception:
            value = '(Error decoding value)'
    return value


def to_string(value):
    try:
        return six.binary_type(value.decode('utf-8').encode('utf-8'))
    except:
        return to_unicode(value).encode('utf-8')


def shorten(var, list_length=50, string_length=200):
    var = transform(var)
    if isinstance(var, six.string_types) and len(var) > string_length:
        var = var[:string_length - 3] + '...'
    elif isinstance(var, (list, tuple, set, frozenset)) and len(var) > list_length:
        # TODO: we should write a real API for storing some metadata with vars when
        # we get around to doing ref storage
        # TODO: when we finish the above, we should also implement this for dicts
        var = list(var)[:list_length] + ['...', '(%d more elements)' % (len(var) - list_length,)]
    return var
