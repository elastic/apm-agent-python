"""
elasticapm.conf.defaults
~~~~~~~~~~~~~~~~~~~

Represents the default values for all ElasticAPM settings.

:copyright: (c) 2011-2017 Elasticsearch

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

import os
import os.path
import socket

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), os.pardir))

# Allow local testing of ElasticAPM even if DEBUG is enabled
DEBUG = False

# Error API path
ERROR_API_PATH = '/v1/errors'

# Transactions API path
TRANSACTIONS_API_PATH = '/v1/transactions'

TIMEOUT = 20

# TODO: this is specific to Django
CLIENT = 'elasticapm.contrib.django.DjangoClient'

HOSTNAME = socket.gethostname()

# Credentials to authenticate with the APM Server server
ACCESS_TOKEN = None

# Extending this allow you to ignore module prefixes when we attempt to
# discover which function an error comes from (typically a view)
EXCLUDE_PATHS = []

# By default ElasticAPM only looks at modules in INSTALLED_APPS for drilling down
# where an exception is located
INCLUDE_PATHS = []

# The maximum number of elements to store for a list-like structure.
MAX_LENGTH_LIST = 50

# The maximum length to store of a string-like structure.
MAX_LENGTH_STRING = 400

MAX_LENGTH_VALUES = {
    'message': 200,
    'server_name': 200,
    'culprit': 100,
    'logger': 60
}

# Automatically log frame stacks from all ``logging`` messages.
AUTO_LOG_STACKS = False

# Client-side data processors to apply
PROCESSORS = (
    'elasticapm.processors.sanitize_stacktrace_locals',
    'elasticapm.processors.sanitize_http_request_cookies',
    'elasticapm.processors.sanitize_http_headers',
    'elasticapm.processors.sanitize_http_wsgi_env',
    'elasticapm.processors.sanitize_http_request_querystring',
    'elasticapm.processors.sanitize_http_request_body',
)

# How often we send data to the metrics backend
TRACES_SEND_FREQ_SECS = 60

# Should data be sent to the APM Server asynchronously in a separate thread
ASYNC_MODE = True

# Should elasticapm wrap middleware for better metrics detection
INSTRUMENT_DJANGO_MIDDLEWARE = True

SYNC_TRANSPORT_CLASS = 'elasticapm.transport.http_urllib3.Urllib3Transport'

ASYNC_TRANSPORT_CLASS = 'elasticapm.transport.http_urllib3.AsyncUrllib3Transport'

TIMESTAMP_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'
