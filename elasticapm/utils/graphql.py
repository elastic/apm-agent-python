def get_graphql_tx_name(query_string, op=None):
    from graphql.language import parser

    doc = parser.parse(query_string)
    op = op or doc.definitions[0].operation
    fields = doc.definitions[0].selection_set.selections
    return "%s %s" % (op.upper(), "+".join([f.name.value for f in fields]))
