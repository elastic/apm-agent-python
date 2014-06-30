"""
opbeat.utils
~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

# import hashlib
# import hmac
# try:
#     import pkg_resources
# except ImportError:
#     pkg_resources = None
# import sys

from opbeat.utils import six

def varmap(func, var, context=None, name=None):
    """
    Executes ``func(key_name, value)`` on all values
    recurisively discovering dict and list scoped
    values.
    """
    if context is None:
        context = {}
    objid = id(var)
    if objid in context:
        return func(name, '<...>')
    context[objid] = 1
    if isinstance(var, dict):
        ret = dict((k, varmap(func, v, context, k)) for k, v in six.iteritems(var))
    elif isinstance(var, (list, tuple)):
        ret = [varmap(func, f, context, name) for f in var]
    else:
        ret = func(name, var)
    del context[objid]
    return ret



# def get_signature(message, timestamp, key):
#     return hmac.new(str(key), '%s %s' % (timestamp, message), hashlib.sha1).hexdigest()


# def get_auth_header(protocol, timestamp, client, access_token=None, signature=None, **kwargs):
#     header = [
#         ('sentry_timestamp', timestamp),
#         ('sentry_client', client),
#         ('sentry_version', protocol),
#     ]
#     if signature:
#         header.append(('sentry_signature', signature))
#     if access_token:
#         header.append(('sentry_key', access_token))

#     return 'Sentry %s' % ', '.join('%s=%s' % (k, v) for k, v in header)
