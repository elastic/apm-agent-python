from elasticapm.contrib.asyncio.traces import async_capture_span
from elasticapm.instrumentation.packages.asyncio.base import AsyncAbstractInstrumentedModule

class AioRedisInstrumentation(AsyncAbstractInstrumentedModule):
    name = "aioredis"

    instrument_list = [("aioredis.Connection", "RedisConnection.execute")]

    async def call(self, module, method, wrapped, instance, args, kwargs):
        command = args[0]
        async with async_capture_span(command, leaf=True, span_type="db", span_subtype="redis"):
            return await wrapped(*args, **kwargs)