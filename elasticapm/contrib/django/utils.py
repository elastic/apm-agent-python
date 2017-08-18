import os

from django.template.base import Node

from elasticapm.utils.stacks import get_frame_info

try:
    from django.template.base import Template
except ImportError:
    class Template(object):
        pass


def linebreak_iter(template_source):
    yield 0
    p = template_source.find('\n')
    while p >= 0:
        yield p + 1
        p = template_source.find('\n', p + 1)
    yield len(template_source) + 1


def get_data_from_template_source(source):
    origin, (start, end) = source
    template_source = origin.reload()

    lineno = None
    upto = 0
    source_lines = []
    for num, next in enumerate(linebreak_iter(template_source)):
        if start >= upto and end <= next:
            lineno = num
        source_lines.append(template_source[upto:next])
        upto = next

    if not source_lines or lineno is None:
        return {}

    pre_context = source_lines[max(lineno - 3, 0):lineno]
    post_context = source_lines[(lineno + 1):(lineno + 4)]
    context_line = source_lines[lineno]

    return {
        'template': {
            'filename': origin.loadname,
            'abs_path': origin.name,
            'pre_context': pre_context,
            'context_line': context_line,
            'lineno': lineno,
            'post_context': post_context,
        },
        'culprit': origin.loadname,
    }


def get_data_from_template_debug(template_debug):
    pre_context = []
    post_context = []
    context_line = None
    for lineno, line in template_debug['source_lines']:
        if lineno < template_debug['line']:
            pre_context.append(line)
        elif lineno > template_debug['line']:
            post_context.append(line)
        else:
            context_line = line
    return {
        'template': {
            'filename': os.path.basename(template_debug['name']),
            'abs_path': template_debug['name'],
            'pre_context': pre_context,
            'context_line': context_line,
            'lineno': template_debug['line'],
            'post_context': post_context,
        },
        'culprit': os.path.basename(template_debug['name']),
    }


def iterate_with_template_sources(frames, extended=True):
    template = None
    for frame, lineno in frames:
        f_code = getattr(frame, 'f_code', None)
        if f_code:
            function = frame.f_code.co_name
            if function == 'render':
                renderer = getattr(frame, 'f_locals', {}).get('self')
                if renderer and isinstance(renderer, Node):
                    if getattr(renderer, "token", None) is not None:
                        if hasattr(renderer, "source"):
                            # up to Django 1.8
                            yield {
                                'lineno': renderer.token.lineno,
                                'filename': renderer.source[0].name
                            }
                        else:
                            template = {'lineno': renderer.token.lineno}
                # Django 1.9 doesn't have the origin on the Node instance,
                # so we have to get it a bit further down the stack from the
                # Template instance
                elif renderer and isinstance(renderer, Template):
                    if template and getattr(renderer, 'origin', None):
                        template['filename'] = renderer.origin.name
                        yield template
                        template = None

        yield get_frame_info(frame, lineno, extended)
