import functools

from elasticapm.traces import capture_span, error_logger, get_transaction
from elasticapm.utils import get_name_from_func


class async_capture_span(capture_span):
    def __call__(self, func):
        self.name = self.name or get_name_from_func(func)

        @functools.wraps(func)
        async def decorated(*args, **kwds):
            async with self:
                return await func(*args, **kwds)

        return decorated

    async def __aenter__(self):
        transaction = get_transaction()
        if transaction and transaction.is_sampled:
            transaction.begin_span(self.name, self.type, context=self.extra, leaf=self.leaf)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        transaction = get_transaction()
        if transaction and transaction.is_sampled:
            try:
                transaction.end_span(self.skip_frames)
            except LookupError:
                error_logger.info("ended non-existing span %s of type %s", self.name, self.type)
