from opbeat_python.base import Client


def get_tempstoreclient(project_id="1", api_key="test_key", **kwargs):
	return TempStoreClient(project_id=project_id, api_key=api_key, **kwargs)

class TempStoreClient(Client):
    def __init__(self, servers=None, project_id=None, api_key=None, **kwargs):
        self.events = []
        super(TempStoreClient, self).__init__(servers=servers, project_id=project_id, api_key=api_key, **kwargs)

    def send(self, **kwargs):
        self.events.append(kwargs)
