from elasticapm.utils.module_import import import_string

_cls_register = {
    "elasticapm.instrumentation.packages.botocore.BotocoreInstrumentation",
    "elasticapm.instrumentation.packages.jinja2.Jinja2Instrumentation",
    "elasticapm.instrumentation.packages.psycopg2.Psycopg2Instrumentation",
    "elasticapm.instrumentation.packages.psycopg2.Psycopg2RegisterTypeInstrumentation",
    "elasticapm.instrumentation.packages.mysql.MySQLInstrumentation",
    "elasticapm.instrumentation.packages.pylibmc.PyLibMcInstrumentation",
    "elasticapm.instrumentation.packages.pymongo.PyMongoInstrumentation",
    "elasticapm.instrumentation.packages.pymongo.PyMongoBulkInstrumentation",
    "elasticapm.instrumentation.packages.pymongo.PyMongoCursorInstrumentation",
    "elasticapm.instrumentation.packages.python_memcached.PythonMemcachedInstrumentation",
    "elasticapm.instrumentation.packages.redis.RedisInstrumentation",
    "elasticapm.instrumentation.packages.redis.RedisPipelineInstrumentation",
    "elasticapm.instrumentation.packages.requests.RequestsInstrumentation",
    "elasticapm.instrumentation.packages.sqlite.SQLiteInstrumentation",
    "elasticapm.instrumentation.packages.urllib3.Urllib3Instrumentation",
    "elasticapm.instrumentation.packages.elasticsearch.ElasticsearchConnectionInstrumentation",
    "elasticapm.instrumentation.packages.elasticsearch.ElasticsearchInstrumentation",
    "elasticapm.instrumentation.packages.cassandra.CassandraInstrumentation",
    "elasticapm.instrumentation.packages.pymssql.PyMSSQLInstrumentation",
    "elasticapm.instrumentation.packages.pyodbc.PyODBCInstrumentation",
    "elasticapm.instrumentation.packages.django.template.DjangoTemplateInstrumentation",
    "elasticapm.instrumentation.packages.django.template.DjangoTemplateSourceInstrumentation",
}


def register(cls):
    _cls_register.add(cls)


_instrumentation_singletons = {}


def get_instrumentation_objects():
    for cls_str in _cls_register:
        if cls_str not in _instrumentation_singletons:
            cls = import_string(cls_str)
            _instrumentation_singletons[cls_str] = cls()

        obj = _instrumentation_singletons[cls_str]
        yield obj
