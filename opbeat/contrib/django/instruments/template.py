from django.template import Template
import time
from opbeat.contrib.django.instruments.aggr import instrumentation
from opbeat.utils.stacks import get_stack_info
from opbeat.utils.stacks import iter_stack_frames


def fake_render(template, *args, **kwargs):
    with instrumentation.time(template.name, "template"):
        # noinspection PyUnresolvedReferences
        out = Template.original_render(template, *args, **kwargs)  # noqa

    return out


def enable_instrumentation():
    if not hasattr(Template, 'original_render'):
        Template.original_render = Template._render
        Template._render = fake_render
