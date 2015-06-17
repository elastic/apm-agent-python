from opbeat.instrumentation import register
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
    for obj in register.get_instrumentation_objects():
        obj.instrument(client)

    wrapt.wrap_function_wrapper('django.template.base',
                                'Parser.extend_nodelist',
                                wrapped_extend_nodelist)
