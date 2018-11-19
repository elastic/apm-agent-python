from elasticapm.traces import get_transaction


def rum_tracing(request):
    transaction = get_transaction()
    if transaction and transaction.trace_parent:
        return {
            "apm": {
                "trace_id": transaction.trace_parent.trace_id,
                # only put the callable into the context to ensure that we only change the span_id if the value
                # is rendered
                "span_id": transaction.ensure_parent_id,
                "is_sampled": transaction.is_sampled,
                "is_sampled_js": "true" if transaction.is_sampled else "false",
            }
        }
    return {}
