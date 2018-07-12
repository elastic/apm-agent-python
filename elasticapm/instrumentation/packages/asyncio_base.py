from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule


class AsyncAbstractInstrumentedModule(AbstractInstrumentedModule):
    async def call(self, module, method, wrapped, instance, args, kwargs):
        raise NotImplementedError()
