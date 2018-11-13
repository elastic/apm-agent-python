import threading

thread_local = threading.local()
thread_local.transaction = None
elasticapm_span_var = None


def get_transaction(clear=False):
    """
    Get the transaction registered for the current thread.

    :return:
    :rtype: Transaction
    """
    transaction = getattr(thread_local, "transaction", None)
    if clear:
        thread_local.transaction = None
    return transaction


def set_transaction(transaction):
    thread_local.transaction = transaction


def get_span():
    return getattr(thread_local, "span", None)


def set_span(span):
    thread_local.span = span
