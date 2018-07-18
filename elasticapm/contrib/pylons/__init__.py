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


def list_from_setting(config, setting):
    value = config.get(setting)
    if not value:
        return None
    return value.split()


class ElasticAPM(Middleware):
    def __init__(self, app, config, client_cls=Client):
        client = client_cls(
            server_url=config.get("elasticapm.server_url"),
            server_timeout=config.get("elasticapm.server_timeout"),
            name=config.get("elasticapm.name"),
            service_name=config.get("elasticapm.service_name"),
            secret_token=config.get("elasticapm.secret_token"),
            include_paths=list_from_setting(config, "elasticapm.include_paths"),
            exclude_paths=list_from_setting(config, "elasticapm.exclude_paths"),
        )
        super(ElasticAPM, self).__init__(app, client)
