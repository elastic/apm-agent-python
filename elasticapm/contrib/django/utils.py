#  BSD 3-Clause License
#
#  Copyright (c) 2019, Elasticsearch BV
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  * Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


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
