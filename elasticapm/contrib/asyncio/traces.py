from elasticapm.traces import capture_span, error_logger, get_transaction


class async_capture_span(capture_span):
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
                error_logger.info('ended non-existing span %s of type %s', self.name, self.type)
