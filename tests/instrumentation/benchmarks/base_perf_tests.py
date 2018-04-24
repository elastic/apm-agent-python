import mock
import pytest

import elasticapm
from tests.instrumentation.benchmarks.perf_util import go_someplace_else


@pytest.mark.parametrize('elasticapm_client', [{
    'include_paths': ('tests.instrumentation.perf_tests', 'instrumentation.perf_tests', 'a.b', 'c.d.e', 'f.g.h.x'),
    'exclude_paths': ('tests.instrumentation.django_tests', 'elasticapm')
}], indirect=True)
def test_stacktrace_performance(elasticapm_client, benchmark):
    with mock.patch('elasticapm.traces.TransactionsStore.should_collect') as should_collect:
        def do_it():
            elasticapm_client.begin_transaction('perf')
            go()
            elasticapm_client.end_transaction('perf', 'OK')
            should_collect.return_value = False
        benchmark.pedantic(do_it, rounds=10, iterations=100)


@pytest.mark.parametrize('django_elasticapm_client', [{
    'include_paths': ('tests.instrumentation.perf_tests', 'instrumentation.perf_tests', 'a.b', 'c.d.e', 'f.g.h.x'),
    'exclude_paths': ('tests.instrumentation.django_tests', 'elasticapm')
}], indirect=True)
def test_stacktrace_performance_django(django_elasticapm_client, benchmark):
    with mock.patch('elasticapm.traces.TransactionsStore.should_collect') as should_collect:
        def do_it():
            django_elasticapm_client.begin_transaction('perf')
            go()
            django_elasticapm_client.end_transaction('perf', 'OK')
            should_collect.return_value = False
        benchmark.pedantic(do_it, rounds=10, iterations=100)


@elasticapm.capture_span()
def go():
    for i in range(5):
        with elasticapm.capture_span('in-go'):
            go_2()
            go_someplace_else()


@elasticapm.capture_span()
def go_2():
    with elasticapm.capture_span('in-go2'):
        pass
