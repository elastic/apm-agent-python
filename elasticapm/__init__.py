"""
elasticapm
~~~~~

:copyright: (c) 2011-2017 Elasticsearch

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

__all__ = ('VERSION', 'Client')

try:
    VERSION = __import__('pkg_resources') \
        .get_distribution('elastic-apm').version
except Exception as e:
    VERSION = 'unknown'

from elasticapm.base import *  # noqa E403
from elasticapm.conf import *  # noqa E403
from elasticapm.instrumentation.control import instrument  # noqa E403
from elasticapm.instrumentation.control import uninstrument  # noqa E403
from elasticapm.traces import *  # noqa E403
