import asyncio
import urllib.parse

from elasticapm.base import Client as BaseClient


class Client(BaseClient):
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
        task = loop.create_task(transport.send(data, headers, timeout=self.config.server_timeout))
        task.add_done_callback(self.handle_transport_response)

    def _start_send_timer(self, timeout=None):
        timeout = timeout or self.config.flush_interval
        self._send_timer = AsyncTimer(timeout, self._collect_transactions)

    def _stop_send_timer(self):
        if self._send_timer:
            self._send_timer.cancel()


class AsyncTimer:
    def __init__(self, interval, callback):
        self.interval = interval
        self.callback = callback
        self.task = asyncio.ensure_future(self._job())
        self._done = False

    async def _job(self):
        await asyncio.sleep(self.interval)
        await self._callback()
        self._done = True

    def cancel(self):
        if not self._done:
            self.task.cancel()
