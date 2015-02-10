from django.template import Template


def fake_render(template, *args, **kwargs):
    from opbeat.contrib.django.models import get_client

    with get_client().captureTrace(template.name, "template"):
        # noinspection PyUnresolvedReferences
        out = Template.original_render(template, *args, **kwargs)  # noqa

    return out


def enable_instrumentation():
    if not hasattr(Template, 'original_render'):
        Template.original_render = Template._render
        Template._render = fake_render
