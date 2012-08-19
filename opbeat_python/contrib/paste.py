from opbeat_python.middleware import Opbeat
from opbeat_python.base import Client


def opbeat_filter_factory(app, global_conf, **kwargs):
    client = Client(**kwargs)
    return Opbeat(app, client)
