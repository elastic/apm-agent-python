import sys

import elasticapm.context
from elasticapm.context.threadlocal import ThreadLocalContext


def test_execution_context_backing():
    execution_context = elasticapm.context.init_execution_context()

    if sys.version_info[0] == 3 and sys.version_info[1] >= 7:
        from elasticapm.context.contextvars import ContextVarsContext

        assert isinstance(execution_context, ContextVarsContext)
    else:
        assert isinstance(execution_context, ThreadLocalContext)


def test_execution_context_monkeypatched(monkeypatch):
    with monkeypatch.context() as m:
        m.setattr(elasticapm.context, "threading_local_monkey_patched", lambda: True)
        execution_context = elasticapm.context.init_execution_context()

    # Should always use ThreadLocalContext when thread local is monkey patched
    assert isinstance(execution_context, ThreadLocalContext)
