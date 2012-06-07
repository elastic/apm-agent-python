"""
opbeat_python.contrib.django.logging
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

import warnings

warnings.warn('opbeat_python.contrib.django.logging is deprecated. Use opbeat_python.contrib.django.handlers instead.', DeprecationWarning)

from opbeat_python.contrib.django.handlers import SentryHandler

__all__ = ('SentryHandler',)
