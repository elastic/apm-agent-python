import threading

from elasticapm.context.base import BaseContext


class ThreadLocalContext(BaseContext):
    thread_local = threading.local()
    thread_local.transaction = None
    thread_local.span = None

    def get_transaction(self, clear=False):
        """
        Get the transaction registered for the current thread.

        :return:
        :rtype: Transaction
        """
        transaction = getattr(self.thread_local, "transaction", None)
        if clear:
            self.thread_local.transaction = None
        return transaction

    def set_transaction(self, transaction):
        self.thread_local.transaction = transaction

    def get_span(self):
        return getattr(self.thread_local, "span", None)

    def set_span(self, span):
        self.thread_local.span = span


execution_context = ThreadLocalContext()
