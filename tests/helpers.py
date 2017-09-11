from elasticapm.base import Client


def get_tempstoreclient(app_name="myapp",
                        secret_token="test_key", **kwargs):
    return TempStoreClient(app_name=app_name, secret_token=secret_token, **kwargs)


class TempStoreClient(Client):
    def __init__(self, **defaults):
        self.events = []
        super(TempStoreClient, self).__init__(**defaults)

    def send(self, **kwargs):
        self.events.append(kwargs)
