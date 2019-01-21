from __future__ import absolute_import

import contextvars
from elasticapm.context.base import BaseContext


class ContextVarsContext(BaseContext):
    elasticapm_transaction_var = contextvars.ContextVar("elasticapm_transaction_var")
    elasticapm_span_var = contextvars.ContextVar("elasticapm_span_var")

    def get_transaction(self, clear=False):
        try:
            transaction = self.elasticapm_transaction_var.get()
            if clear:
                self.set_transaction(None)
            return transaction
        except LookupError:
            return None

    def set_transaction(self, transaction):
        self.elasticapm_transaction_var.set(transaction)

    def get_span(self):
        try:
            return self.elasticapm_span_var.get()
        except LookupError:
            return None

    def set_span(self, span):
        self.elasticapm_span_var.set(span)


execution_context = ContextVarsContext()
