from opbeat.instrumentation.packages.redis import RedisInstrumentation
from opbeat.instrumentation.packages.requests import RequestsInstrumentation
from opbeat.instrumentation.packages.pylibmc import PyLibMcInstrumentation
from opbeat.instrumentation.packages.django.template import DjangoTemplateInstrumentation
from opbeat.instrumentation.packages.psycopg2 import Psycopg2Instrumentation
from opbeat.instrumentation.packages.urllib3 import Urllib3Instrumentation
from opbeat.utils import wrapt


def wrapped_extend_nodelist(wrapped, instance, args, kwargs):
    wrapped(*args, **kwargs)

    if len(args) > 0:
        node = args[1]
    else:
        node = kwargs['node']

    if len(args) > 1:
        token = args[2]
    else:
        token = kwargs['token']

    if not hasattr(node, 'token'):
        node.token = token

    return node


def instrument(client):
    for cls in [RequestsInstrumentation, PyLibMcInstrumentation,
                DjangoTemplateInstrumentation, Psycopg2Instrumentation,
                RedisInstrumentation, Urllib3Instrumentation]:

        cls(client).instrument()

    wrapt.wrap_function_wrapper('django.template.base',
                                'Parser.extend_nodelist',
                                wrapped_extend_nodelist)