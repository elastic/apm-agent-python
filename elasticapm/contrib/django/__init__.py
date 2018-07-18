"""
elasticapm.contrib.django
~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2017 Elasticsearch

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""
from elasticapm.contrib.django.client import *  # noqa E401

default_app_config = "elasticapm.contrib.django.apps.ElasticAPMConfig"
