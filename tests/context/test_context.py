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

import sys

import mock
import pytest

import elasticapm.context
from elasticapm.context.contextvars import ContextVarsContext
from elasticapm.context.threadlocal import ThreadLocalContext
from elasticapm.traces import Span


def test_execution_context_backing():
    execution_context = elasticapm.context.init_execution_context()

    if sys.version_info[0] == 3 and sys.version_info[1] >= 7:
        from elasticapm.context.contextvars import ContextVarsContext

        assert isinstance(execution_context, ContextVarsContext)
    else:
        try:
            import opentelemetry

            pytest.skip(
                "opentelemetry installs contextvars backport, so this test isn't valid for the opentelemetry matrix"
            )
        except ImportError:
            pass

        assert isinstance(execution_context, ThreadLocalContext)


def test_execution_context_monkeypatched(monkeypatch):
    with monkeypatch.context() as m:
        m.setattr(elasticapm.context, "threading_local_monkey_patched", lambda: True)
        execution_context = elasticapm.context.init_execution_context()

    # Should always use ThreadLocalContext when thread local is monkey patched
    assert isinstance(execution_context, ThreadLocalContext)


def test_none_spans_should_not_raise_a_type_error_on_set_span():
    context = ContextVarsContext()
    context.elasticapm_spans_var.set(None)

    context.set_span(mock.MagicMock(spec=Span))

    assert context.get_span() is not None
