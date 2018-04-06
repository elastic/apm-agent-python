from __future__ import absolute_import

import json
import logging

import elasticapm
from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.utils import compat

logger = logging.getLogger(__name__)


class ElasticsearchIndicesIntrumentation(AbstractInstrumentedModule):
    name = 'elasticsearch.index'

    instrument_list = [
        ("elasticsearch.client.indices", "IndicesClient.create"),
        ("elasticsearch.client.indices", "IndicesClient.get"),
        ("elasticsearch.client.indices", "IndicesClient.open"),
        ("elasticsearch.client.indices", "IndicesClient.close"),
        ("elasticsearch.client.indices", "IndicesClient.delete"),
        ("elasticsearch.client.indices", "IndicesClient.exists"),
        ("elasticsearch.client.indices", "IndicesClient.analyze"),
        ("elasticsearch.client.indices", "IndicesClient.refresh"),
        ("elasticsearch.client.indices", "IndicesClient.flush"),
    ]

    def call(self, module, method, wrapped, instance, args, kwargs):
        cls_name, method_name = method.split('.', 1)
        signature = '.'.join([instance.full_name, method_name])
        with elasticapm.capture_span(signature, "db.elasticsearch.index", leaf=True):
            return wrapped(*args, **kwargs)


class ElasticsearchInstrumentation(AbstractInstrumentedModule):
    name = 'elasticsearch'

    # The positional arguments between Elasticsearch major versions do
    # change some times, and are not discoverable at runtime due to
    # a decorator hiding the real signatures. Unfortunately, this leaves
    # us only with the option of keeping our own lookup table for the different
    # versions
    method_args = {
        2: {
            'count_percolate': ['index', 'doc_type', 'id', 'body', 'params'],
            'create': ['index', 'doc_type', 'body', 'id', 'params'],
            'delete_script': ['lang', 'id', 'params'],
            'delete_template': ['id', 'params'],
            'field_stats': ['index', 'body', 'params'],
            'get': ['index', 'id', 'doc_type', 'params'],
            'get_script': ['lang', 'id', 'params'],
            'mpercolate': ['body', 'index', 'doc_type', 'params'],
            'percolate': ['index', 'doc_type', 'id', 'body', 'params'],
            'put_script': ['lang', 'id', 'body', 'params'],
            'search_exists': ['index', 'doc_type', 'body', 'params'],
            'suggest': ['body', 'index', 'params'],
        },
        5: {
            'count_percolate': ['index', 'doc_type', 'id', 'body', 'params'],
            'create': ['index', 'doc_type', 'id', 'body', 'params'],
            'delete_script': ['lang', 'id', 'params'],
            'delete_template': ['id', 'params'],
            'field_stats': ['index', 'body', 'params'],
            'get': ['index', 'id', 'doc_type', 'params'],
            'get_script': ['lang', 'id', 'params'],
            'mpercolate': ['body', 'index', 'doc_type', 'params'],
            'percolate': ['index', 'doc_type', 'id', 'body', 'params'],
            'put_script': ['lang', 'id', 'body', 'params'],
            'suggest': ['body', 'index', 'params'],
        },
        6: {
            'create': ['index', 'doc_type', 'id', 'body', 'params'],
            'delete_script': ['id', 'params'],
            'get': ['index', 'doc_type', 'id', 'params'],
            'get_script': ['id', 'params'],
            'put_script': ['id', 'body', 'context', 'params'],
        },
        'all': {
            'bulk': ['body', 'index', 'doc_type', 'params'],
            'clear_scroll': ['scroll_id', 'body', 'params'],
            'count': ['index', 'doc_type', 'body', 'params'],
            'delete': ['index', 'doc_type', 'id', 'params'],
            'delete_by_query': ['index', 'body', 'doc_type', 'params'],
            'exists': ['index', 'doc_type', 'id', 'params'],
            'exists_source': ['index', 'doc_type', 'id', 'params'],
            'explain': ['index', 'doc_type', 'id', 'body', 'params'],
            'field_caps': ['index', 'body', 'params'],
            'get_source': ['index', 'doc_type', 'id', 'params'],
            'get_template': ['id', 'params'],
            'index': ['index', 'doc_type', 'body', 'id', 'params'],
            'info': ['params'],
            'mget': ['body', 'index', 'doc_type', 'params'],
            'msearch': ['body', 'index', 'doc_type', 'params'],
            'msearch_template': ['body', 'index', 'doc_type', 'params'],
            'mtermvectors': ['index', 'doc_type', 'body', 'params'],
            'ping': ['params'],
            'put_template': ['id', 'body', 'params'],
            'reindex': ['body', 'params'],
            'reindex_rethrottle': ['task_id', 'params'],
            'render_search_template': ['id', 'body', 'params'],
            'scroll': ['scroll_id', 'body', 'params'],
            'search': ['index', 'doc_type', 'body', 'params'],
            'search_shards': ['index', 'doc_type', 'params'],
            'search_template': ['index', 'doc_type', 'body', 'params'],
            'termvectors': ['index', 'doc_type', 'id', 'body', 'params'],
            'update': ['index', 'doc_type', 'id', 'body', 'params'],
            'update_by_query': ['index', 'doc_type', 'body', 'params'],
        }
    }

    query_methods = ('search', 'count', 'delete_by_query')

    instrument_list = [
        ("elasticsearch.client", "Elasticsearch.ping"),
        ("elasticsearch.client", "Elasticsearch.info"),
        ("elasticsearch.client", "Elasticsearch.create"),
        ("elasticsearch.client", "Elasticsearch.index"),
        ("elasticsearch.client", "Elasticsearch.count"),
        ("elasticsearch.client", "Elasticsearch.delete"),
        ("elasticsearch.client", "Elasticsearch.delete_by_query"),
        ("elasticsearch.client", "Elasticsearch.exists"),
        ("elasticsearch.client", "Elasticsearch.exists_source"),
        ("elasticsearch.client", "Elasticsearch.get"),
        ("elasticsearch.client", "Elasticsearch.get_source"),
        ("elasticsearch.client", "Elasticsearch.search"),
        ("elasticsearch.client", "Elasticsearch.update"),

        # TODO:
        # ("elasticsearch.client", "Elasticsearch.update_by_query"),
        # ("elasticsearch.client", "Elasticsearch.search_shards"),
        # ("elasticsearch.client", "Elasticsearch.put_script"),
        # ("elasticsearch.client", "Elasticsearch.get_script"),
        # ("elasticsearch.client", "Elasticsearch.delete_script"),
        # ("elasticsearch.client", "Elasticsearch.put_template"),
        # ("elasticsearch.client", "Elasticsearch.get_template"),
        # ("elasticsearch.client", "Elasticsearch.explain"),
        # ("elasticsearch.client", "Elasticsearch.termvectors"),
        # ("elasticsearch.client", "Elasticsearch.mtermvectors"),
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
        cls_name, method_name = method.split('.', 1)
        positional_args = (self.method_args['all'].get(method_name) or
                           self.method_args[self.version].get(method_name) or [])
        signature = ['ES', method_name]
        for arg_name in ('index', 'doc_type', 'id'):
            if arg_name in kwargs:
                arg_value = kwargs[arg_name]
            else:
                try:
                    arg_value = args[positional_args.index(arg_name)]
                    if isinstance(arg_value, (list, tuple)):
                        arg_value = ','.join(arg_value)
                except (IndexError, ValueError):
                    # ValueError is raised if this method doesn't have a position
                    # argument with arg_value
                    # IndexError is raised if the method was called without this
                    # positional argument
                    arg_value = None
            if arg_value:
                if isinstance(arg_value, (list, tuple)):
                    arg_value = ','.join(compat.text_type(v) for v in arg_value)
                signature.append('='.join((arg_name, compat.text_type(arg_value))))
        body = kwargs.get('body')
        if not body:
            try:
                body = args[positional_args.index('body')]
            except (IndexError, ValueError):
                pass
        context = {'db': {'type': 'elasticsearch'}}
        if method_name in self.query_methods:
            query = []
            # using both q AND body is allowed in some API endpoints / ES versions,
            # but not in others. We simply capture both if they are there so the
            # user can see it.
            if 'q' in kwargs:
                query.append('q=' + kwargs['q'])
            if isinstance(body, dict) and 'query' in body:
                query.append(json.dumps(body['query']))
            context['db']['statement'] = '\n\n'.join(query)
        if method_name == 'update':
            if isinstance(body, dict) and 'script' in body:
                context['db']['statement'] = json.dumps(body)
        with elasticapm.capture_span(' '.join(signature), "db.elasticsearch", context, leaf=True):
            return wrapped(*args, **kwargs)
