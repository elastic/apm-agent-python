from opbeat.base import Client


def get_tempstoreclient(app_name="myapp",
                        secret_token="test_key", **kwargs):
    return TempStoreClient(app_name=app_name, secret_token=secret_token, **kwargs)


class TempStoreClient(Client):
    def __init__(self,
                 servers=None, app_name=None,
                 secret_token=None, **kwargs):
        self.events = []
        super(TempStoreClient, self).__init__(
            servers=servers, app_id=app_name,
            secret_token=secret_token, **kwargs)

    def send(self, **kwargs):
        self.events.append(kwargs)
