import asyncio

from elasticapm.base import Client as BaseClient


class Client(BaseClient):
    def _start_send_timer(self, timeout=None):
        timeout = timeout or self.config.api_request_time
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
        await asyncio.sleep(self.interval * 0.001)
        await self._callback()
        self._done = True

    def cancel(self):
        if not self._done:
            self.task.cancel()
