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

from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.traces import capture_span


class DjangoTemplateInstrumentation(AbstractInstrumentedModule):
    name = "django_template"

    instrument_list = [("django.template", "Template.render")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        name = getattr(instance, "name", None)

        if not name:
            name = "<template string>"
        with capture_span(name, span_type="template", span_subtype="django", span_action="render"):
            return wrapped(*args, **kwargs)


class DjangoTemplateSourceInstrumentation(AbstractInstrumentedModule):
    name = "django_template_source"
    instrument_list = [("django.template.base", "Parser.extend_nodelist")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        ret = wrapped(*args, **kwargs)

        if len(args) > 1:
            node = args[1]
        elif "node" in kwargs:
            node = kwargs["node"]
        else:
            return ret

        if len(args) > 2:
            token = args[2]
        elif "token" in kwargs:
            token = kwargs["token"]
        else:
            return ret

        if not hasattr(node, "token") and hasattr(token, "lineno"):
            node.token = token

        return ret
