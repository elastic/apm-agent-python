import asyncio
import urllib.parse

from opbeat.base import Client


class Client(Client):

    def handle_transport_response(self, task):
        try:
            url = task.result()
        except Exception as exc:
            self.handle_transport_fail(exception=exc)
        else:
            self.handle_transport_success(url=url)

    def _send_remote(self, url, data, headers=None):
        if headers is None:
            headers = {}
        parsed = urllib.parse.urlparse(url)
        transport = self._get_transport(parsed)
        loop = asyncio.get_event_loop()
        task = loop.create_task(
            transport.send(data, headers, timeout=self.timeout))
        task.add_done_callback(self.handle_transport_response)
