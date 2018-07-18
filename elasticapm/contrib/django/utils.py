from django.template.base import Node

from elasticapm.utils.stacks import get_frame_info

try:
    from django.template.base import Template
except ImportError:

    class Template(object):
        pass


def iterate_with_template_sources(
    frames,
    with_locals=True,
    library_frame_context_lines=None,
    in_app_frame_context_lines=None,
    include_paths_re=None,
    exclude_paths_re=None,
    locals_processor_func=None,
):
    template = None
    for frame, lineno in frames:
        f_code = getattr(frame, "f_code", None)
        if f_code:
            function_name = frame.f_code.co_name
            if function_name == "render":
                renderer = getattr(frame, "f_locals", {}).get("self")
                if renderer and isinstance(renderer, Node):
                    if getattr(renderer, "token", None) is not None:
                        if hasattr(renderer, "source"):
                            # up to Django 1.8
                            yield {"lineno": renderer.token.lineno, "filename": renderer.source[0].name}
                        else:
                            template = {"lineno": renderer.token.lineno}
                # Django 1.9 doesn't have the origin on the Node instance,
                # so we have to get it a bit further down the stack from the
                # Template instance
                elif renderer and isinstance(renderer, Template):
                    if template and getattr(renderer, "origin", None):
                        template["filename"] = renderer.origin.name
                        yield template
                        template = None

        yield get_frame_info(
            frame,
            lineno,
            library_frame_context_lines=library_frame_context_lines,
            in_app_frame_context_lines=in_app_frame_context_lines,
            with_locals=with_locals,
            include_paths_re=include_paths_re,
            exclude_paths_re=exclude_paths_re,
            locals_processor_func=locals_processor_func,
        )
