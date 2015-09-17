from opbeat.utils.module_import import import_string

_cls_register = set([
    'opbeat.instrumentation.packages.jinja2.Jinja2Instrumentation',
    'opbeat.instrumentation.packages.psycopg2.Psycopg2Instrumentation',
    'opbeat.instrumentation.packages.psycopg2.Psycopg2RegisterTypeInstrumentation',
    'opbeat.instrumentation.packages.mysql.MySQLInstrumentation',
    'opbeat.instrumentation.packages.pylibmc.PyLibMcInstrumentation',
    'opbeat.instrumentation.packages.python_memcached.PythonMemcachedInstrumentation',
    'opbeat.instrumentation.packages.redis.RedisInstrumentation',
    'opbeat.instrumentation.packages.redis.RedisPipelineInstrumentation',
    'opbeat.instrumentation.packages.requests.RequestsInstrumentation',
    'opbeat.instrumentation.packages.sqlite.SQLiteInstrumentation',
    'opbeat.instrumentation.packages.urllib3.Urllib3Instrumentation',

    'opbeat.instrumentation.packages.django.template.DjangoTemplateInstrumentation',
    'opbeat.instrumentation.packages.django.template.DjangoTemplateSourceInstrumentation',
])

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
