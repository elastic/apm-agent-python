"""
opbeat.conf
~~~~~~~~~~

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

import logging

__all__ = ('setup_logging', )


def setup_logging(handler, exclude=['opbeat',
                                    'gunicorn',
                                    'south',
                                    'opbeat.errors']):
    """
    Configures logging to pipe to Opbeat.

    - ``exclude`` is a list of loggers that shouldn't go to Opbeat.

    For a typical Python install:

    >>> from opbeat.handlers.logging import OpbeatHandler
    >>> client = Opbeat(...)
    >>> setup_logging(OpbeatHandler(client))

    Within Django:

    >>> from opbeat.contrib.django.logging import OpbeatHandler
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
