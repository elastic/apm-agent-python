"""
opbeat_python
~~~~~

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

__all__ = ('VERSION', 'Client', 'load')

try:
    VERSION = __import__('pkg_resources') \
        .get_distribution('opbeat_python').version
except Exception, e:
    VERSION = 'unknown'

from base import *
from conf import *
