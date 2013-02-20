from opbeat.middleware import Opbeat
from opbeat.base import Client


def opbeat_filter_factory(app, global_conf, **kwargs):
    client = Client(**kwargs)
    return Opbeat(app, client)
