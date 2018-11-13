from elasticapm.traces import get_transaction


def rum_tracing(request):
    transaction = get_transaction()
    if transaction.trace_parent:
        return {
            "apm": {
                "trace_id": transaction.trace_parent.trace_id,
                "span_id": lambda: transaction.ensure_parent_id(),
                "is_sampled": transaction.is_sampled,
                "is_sampled_js": "true" if transaction.is_sampled else "false",
            }
        }
    return {}
