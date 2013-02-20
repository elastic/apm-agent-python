"""
opbeat.contrib.pylons
~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""
from opbeat.middleware import Opbeat as Middleware
from opbeat.base import Client


def list_from_setting(config, setting):
    value = config.get(setting)
    if not value:
        return None
    return value.split()


class Opbeat(Middleware):
    def __init__(self, app, config, client_cls=Client):
        client = client_cls(
            servers=list_from_setting(config, 'opbeat.servers'),
            name=config.get('opbeat.name'),
            project_id=config.get('opbeat.project_id'),
            access_token=config.get('opbeat.access_token'),
            include_paths=list_from_setting(config, 'opbeat.include_paths'),
            exclude_paths=list_from_setting(config, 'opbeat.exclude_paths'),
        )
        super(Opbeat, self).__init__(app, client)
