from opbeat_python.base import Client


def get_tempstoreclient(project_id="1", access_token="test_key", **kwargs):
	return TempStoreClient(project_id=project_id,
							access_token=access_token, **kwargs)


class TempStoreClient(Client):
	def __init__(self,
				servers=None, project_id=None,
				access_token=None, **kwargs):
		self.events = []
		super(TempStoreClient, self).__init__(
								servers=servers, project_id=project_id,
								access_token=access_token, **kwargs)

	def send(self, **kwargs):
		self.events.append(kwargs)
