from opbeat_python.middleware import Sentry
from opbeat_python.base import Client


def sentry_filter_factory(app, global_conf, **kwargs):
    client = Client(**kwargs)
    return Sentry(app, client)
