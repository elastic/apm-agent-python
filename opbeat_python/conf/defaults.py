"""
opbeat_python.conf.defaults
~~~~~~~~~~~~~~~~~~~

Represents the default values for all Sentry settings.

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

import os
import os.path
import socket

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), os.pardir))

# Allow local testing of Sentry even if DEBUG is enabled
DEBUG = False

# This should be the full URL to sentries store view
SERVERS = ['https://www.opbeat.com/api/v1/errorlog/']

TIMEOUT = 5

# TODO: this is specific to Django
CLIENT = 'opbeat_python.contrib.django.DjangoClient'

NAME = socket.gethostname()

# Credentials to authenticate with the Sentry server
API_KEY = None

# We allow setting the site name either by explicitly setting it with the
# SENTRY_SITE setting, or using the django.contrib.sites framework for
# fetching the current site. Since we can't reliably query the database
# from this module, the specific logic is within the SiteFilter
SITE = None

# Extending this allow you to ignore module prefixes when we attempt to
# discover which function an error comes from (typically a view)
EXCLUDE_PATHS = []

# By default Sentry only looks at modules in INSTALLED_APPS for drilling down
# where an exception is located
INCLUDE_PATHS = []

# The maximum number of elements to store for a list-like structure.
MAX_LENGTH_LIST = 50

# The maximum length to store of a string-like structure.
MAX_LENGTH_STRING = 400

# Automatically log frame stacks from all ``logging`` messages.
AUTO_LOG_STACKS = False

# Client-side data processors to apply
PROCESSORS = (
    'opbeat_python.processors.SanitizePasswordsProcessor',
)
