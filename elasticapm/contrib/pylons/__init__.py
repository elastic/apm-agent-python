"""
elasticapm.contrib.pylons
~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2017 Elasticsearch

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""
from elasticapm.base import Client
from elasticapm.middleware import ElasticAPM as Middleware
from elasticapm.utils import compat


def list_from_setting(config, setting):
    value = config.get(setting)
    if not value:
        return None
    return value.split()


class ElasticAPM(Middleware):
    def __init__(self, app, config, client_cls=Client):
        client_config = {key[11:]: val for key, val in compat.iteritems(config) if key.startswith("elasticapm.")}
        client = client_cls(**client_config)
        super(ElasticAPM, self).__init__(app, client)
