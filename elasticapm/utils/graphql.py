def get_graphql_tx_name(graphql_doc):
    op = graphql_doc.definitions[0].operation
    fields = graphql_doc.definitions[0].selection_set.selections
    return "%s %s" % (op.upper(), "+".join([f.name.value for f in fields]))
