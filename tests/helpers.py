from opbeat.base import Client


def get_tempstoreclient(organization_id="1", app_id="2",
                        secret_token="test_key", **kwargs):
    return TempStoreClient(organization_id=organization_id, app_id=app_id,
                           secret_token=secret_token, **kwargs)


class TempStoreClient(Client):
    def __init__(self,
                servers=None, organization_id=None, app_id=None,
                secret_token=None, **kwargs):
        self.events = []
        super(TempStoreClient, self).__init__(
            servers=servers, organization_id=organization_id, app_id=app_id,
            secret_token=secret_token, append_http_method_names=True, **kwargs)

    def send(self, **kwargs):
        self.events.append(kwargs)
