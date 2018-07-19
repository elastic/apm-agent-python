from __future__ import absolute_import

import contextvars

elasticapm_transaction_var = contextvars.ContextVar("elasticapm_transaction_var")
elasticapm_span_var = contextvars.ContextVar("elasticapm_span_var")


def get_transaction(clear=False):
    try:
        transaction = elasticapm_transaction_var.get()
        if clear:
            set_transaction(None)
        return transaction
    except LookupError:
        return None


def set_transaction(transaction):
    elasticapm_transaction_var.set(transaction)


def get_span():
    try:
        return elasticapm_span_var.get()
    except LookupError:
        return None


def set_span(span):
    elasticapm_span_var.set(span)
