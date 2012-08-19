"""
opbeat_python.conf
~~~~~~~~~~

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

import logging
import urlparse


__all__ = ('load', 'setup_logging')


# TODO (vng): this seems weirdly located in opbeat_python.conf.  Seems like
# it's really a part of opbeat_python.transport.TransportRegistry
# Not quite sure what to do with this
def load(dsn, scope=None, transport_registry=None):
    """
    Parses a Sentry compatible DSN and loads it
    into the given scope.

    >>> import opbeat_python

    >>> dsn = 'https://public_key:secret_key@sentry.local/project_id'

    >>> # Apply configuration to local scope
    >>> opbeat_python.load(dsn, locals())

    >>> # Return DSN configuration
    >>> options = opbeat_python.load(dsn)
    """

    if not transport_registry:
        from opbeat_python.transport import TransportRegistry
        transport_registry = TransportRegistry()

    url = urlparse.urlparse(dsn)

    if not transport_registry.supported_scheme(url.scheme):
        raise ValueError('Unsupported Sentry DSN scheme: %r' % url.scheme)

    if scope is None:
        scope = {}
    scope_extras = transport_registry.compute_scope(url, scope)
    scope.update(scope_extras)

    return scope


def setup_logging(handler, exclude=['opbeat_python',
                                    'gunicorn',
                                    'south',
                                    'sentry.errors']):
    """
    Configures logging to pipe to Sentry.

    - ``exclude`` is a list of loggers that shouldn't go to Sentry.

    For a typical Python install:

    >>> from opbeat_python.handlers.logging import OpbeatHandler
    >>> client = Sentry(...)
    >>> setup_logging(OpbeatHandler(client))

    Within Django:

    >>> from opbeat_python.contrib.django.logging import OpbeatHandler
    >>> setup_logging(OpbeatHandler())

    Returns a boolean based on if logging was configured or not.
    """
    logger = logging.getLogger()
    if handler.__class__ in map(type, logger.handlers):
        return False

    logger.addHandler(handler)

    # Add StreamHandler to sentry's default so you can catch missed exceptions
    for logger_name in exclude:
        logger = logging.getLogger(logger_name)
        logger.propagate = False
        logger.addHandler(logging.StreamHandler())

    return True
