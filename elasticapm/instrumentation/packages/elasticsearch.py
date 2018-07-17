from __future__ import absolute_import

import json
import logging

import elasticapm
from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule

logger = logging.getLogger(__name__)


API_METHOD_KEY_NAME = "__elastic_apm_api_method_name"
BODY_REF_NAME = "__elastic_apm_body_ref"


class ElasticsearchConnectionInstrumentation(AbstractInstrumentedModule):
    name = "elasticsearch_connection"

    instrument_list = [
        ("elasticsearch.connection.http_urllib3", "Urllib3HttpConnection.perform_request"),
        ("elasticsearch.connection.http_requests", "RequestsHttpConnection.perform_request"),
    ]

    query_methods = ("Elasticsearch.search", "Elasticsearch.count", "Elasticsearch.delete_by_query")

    def call(self, module, method, wrapped, instance, args, kwargs):
        args_len = len(args)
        http_method = args[0] if args_len else kwargs.get("method")
        http_path = args[1] if args_len > 1 else kwargs.get("url")
        params = args[2] if args_len > 2 else kwargs.get("params")
        body = params.pop(BODY_REF_NAME, None) if params else None

        api_method = params.pop(API_METHOD_KEY_NAME, None) if params else None

        signature = "ES %s %s" % (http_method, http_path)
        context = {"db": {"type": "elasticsearch"}}
        if api_method in self.query_methods:
            query = []
            # using both q AND body is allowed in some API endpoints / ES versions,
            # but not in others. We simply capture both if they are there so the
            # user can see it.
            if params and "q" in params:
                # 'q' is already encoded to a byte string at this point
                # we assume utf8, which is the default
                query.append("q=" + params["q"].decode("utf-8", errors="replace"))
            if isinstance(body, dict) and "query" in body:
                query.append(json.dumps(body["query"]))
            context["db"]["statement"] = "\n\n".join(query)
        elif api_method == "Elasticsearch.update":
            if isinstance(body, dict) and "script" in body:
                # only get the `script` field from the body
                context["db"]["statement"] = json.dumps({"script": body["script"]})
        # TODO: add instance.base_url to context once we agreed on a format
        with elasticapm.capture_span(signature, "db.elasticsearch", extra=context, skip_frames=2, leaf=True):
            return wrapped(*args, **kwargs)


class ElasticsearchInstrumentation(AbstractInstrumentedModule):
    name = "elasticsearch"

    body_positions = {
        2: {
            "count_percolate": 3,
            "create": 2,
            "field_stats": 1,
            "mpercolate": 0,
            "percolate": 3,
            "put_script": 2,
            "search_exists": 2,
            "suggest": 0,
        },
        5: {
            "count_percolate": 3,
            "create": 3,
            "field_stats": 1,
            "mpercolate": 0,
            "percolate": 3,
            "put_script": 2,
            "suggest": 0,
        },
        6: {"create": 3, "put_script": 1},
        "all": {
            "bulk": 0,
            "clear_scroll": 1,
            "count": 2,
            "delete_by_query": 1,
            "explain": 3,
            "field_caps": 1,
            "index": 2,
            "mget": 0,
            "msearch": 0,
            "msearch_template": 0,
            "mtermvectors": 2,
            "put_template": 1,
            "reindex": 0,
            "render_search_template": 1,
            "scroll": 1,
            "search": 2,
            "search_template": 2,
            "termvectors": 3,
            "update": 3,
            "update_by_query": 2,
        },
    }

    instrument_list = [
        ("elasticsearch.client", "Elasticsearch.delete_by_query"),
        ("elasticsearch.client", "Elasticsearch.search"),
        ("elasticsearch.client", "Elasticsearch.count"),
        ("elasticsearch.client", "Elasticsearch.update"),
    ]

    def __init__(self):
        super(ElasticsearchInstrumentation, self).__init__()
        try:
            from elasticsearch import VERSION

            self.version = VERSION[0]
        except ImportError:
            self.version = None

    def instrument(self):
        if self.version and not 2 <= self.version < 7:
            logger.debug("Instrumenting version %s of Elasticsearch is not supported by Elastic APM", self.version)
            return
        super(ElasticsearchInstrumentation, self).instrument()

    def call(self, module, method, wrapped, instance, args, kwargs):
        params = kwargs.pop("params", {})

        # make a copy of params in case the caller reuses them for some reason
        params = params.copy() if params is not None else {}

        cls_name, method_name = method.split(".", 1)
        body_pos = (
            self.body_positions["all"].get(method_name) or self.body_positions[self.version].get(method_name) or None
        )

        # store a reference to the non-serialized body so we can use it in the connection layer
        body = args[body_pos] if (body_pos is not None and len(args) > body_pos) else kwargs.get("body")
        params[BODY_REF_NAME] = body
        params[API_METHOD_KEY_NAME] = method

        kwargs["params"] = params
        return wrapped(*args, **kwargs)
