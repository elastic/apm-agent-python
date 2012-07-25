"""
opbeat_python.contrib.pylons
~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""
from opbeat_python.middleware import Sentry as Middleware
from opbeat_python.base import Client


def list_from_setting(config, setting):
    value = config.get(setting)
    if not value:
        return None
    return value.split()


class Sentry(Middleware):
    def __init__(self, app, config, client_cls=Client):
        client = client_cls(
            servers=list_from_setting(config, 'sentry.servers'),
            name=config.get('sentry.name'),
            # key=config.get('sentry.key'),
            project_id=config.get('sentry.project_id'),
            access_token=config.get('sentry.access_token'),
            # project=config.get('sentry.project'),
            # site=config.get('sentry.site'),
            include_paths=list_from_setting(config, 'sentry.include_paths'),
            exclude_paths=list_from_setting(config, 'sentry.exclude_paths'),
        )
        super(Sentry, self).__init__(app, client)
