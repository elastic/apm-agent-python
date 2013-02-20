"""
opbeat.contrib.django.logging
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

import warnings

warnings.warn('opbeat.contrib.django.logging is deprecated. Use opbeat.contrib.django.handlers instead.', DeprecationWarning)

from opbeat.contrib.django.handlers import OpbeatHandler

__all__ = ('OpbeatHandler',)
