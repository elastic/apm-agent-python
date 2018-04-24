import pytest  # isort:skip
django = pytest.importorskip("django")  # isort:skip

import mock

from django.test.utils import override_settings

from tests.utils.compat import middleware_setting

try:
    # Django 1.10+
    from django.urls import reverse
except ImportError:
    from django.core.urlresolvers import reverse


@pytest.mark.parametrize('django_elasticapm_client', [{'_wait_to_first_send': 100}], indirect=True)
def test_perf_template_render(benchmark, client, django_elasticapm_client):
    with mock.patch("elasticapm.traces.TransactionsStore.should_collect") as should_collect:
        should_collect.return_value = False
        with override_settings(**middleware_setting(django.VERSION,
                                                    ['elasticapm.contrib.django.middleware.TracingMiddleware'])):
            resp = benchmark(client.get, reverse("render-heavy-template"))
            assert resp.status_code == 200

    transactions = django_elasticapm_client.instrumentation_store.get_all()

    for transaction in transactions:
        assert len(transaction['spans']) == 2
        assert transaction['result'] == 'HTTP 2xx'


@pytest.mark.parametrize('django_elasticapm_client', [{'_wait_to_first_send': 100}], indirect=True)
def test_perf_template_render_no_middleware(benchmark, client, django_elasticapm_client):
    responses = []
    with mock.patch(
            "elasticapm.traces.TransactionsStore.should_collect") as should_collect:
        should_collect.return_value = False
        resp = benchmark(client.get, reverse("render-heavy-template"))
        assert resp.status_code == 200

    transactions = django_elasticapm_client.instrumentation_store.get_all()
    assert len(transactions) == 0


@pytest.mark.parametrize('django_elasticapm_client', [{'_wait_to_first_send': 100}], indirect=True)
@pytest.mark.django_db(transaction=True)
def test_perf_database_render(benchmark, client, django_elasticapm_client):
    django_elasticapm_client.instrumentation_store.get_all()

    with mock.patch("elasticapm.traces.TransactionsStore.should_collect") as should_collect:
        should_collect.return_value = False

        with override_settings(**middleware_setting(django.VERSION,
                                                    ['elasticapm.contrib.django.middleware.TracingMiddleware'])):
            resp = benchmark(client.get, reverse("render-user-template"))
            assert resp.status_code == 200

        transactions = django_elasticapm_client.instrumentation_store.get_all()

        for transaction in transactions:
            assert len(transaction['spans']) in (102, 103)


@pytest.mark.django_db
@pytest.mark.parametrize('django_elasticapm_client', [{'_wait_to_first_send': 100}], indirect=True)
def test_perf_database_render_no_instrumentation(benchmark, django_elasticapm_client, client):
    django_elasticapm_client.instrumentation_store.get_all()
    with mock.patch("elasticapm.traces.TransactionsStore.should_collect") as should_collect:
        should_collect.return_value = False

        resp = benchmark(client.get, reverse("render-user-template"))
        assert resp.status_code == 200

        transactions = django_elasticapm_client.instrumentation_store.get_all()
        assert len(transactions) == 0


@pytest.mark.django_db
@pytest.mark.parametrize('django_elasticapm_client', [{
    '_wait_to_first_send': 100,
    'flush_interval': 100
}], indirect=True)
def test_perf_transaction_with_collection(benchmark, django_elasticapm_client, client):
    django_elasticapm_client.instrumentation_store.get_all()
    with mock.patch("elasticapm.traces.TransactionsStore.should_collect") as should_collect:
        should_collect.return_value = False
        django_elasticapm_client.events = []

        with override_settings(**middleware_setting(django.VERSION,
                                                    ['elasticapm.contrib.django.middleware.TracingMiddleware'])):
            for i in range(10):
                resp = client.get(reverse("render-user-template"))
                assert resp.status_code == 200

        assert len(django_elasticapm_client.events) == 0

        # Force collection on next request
        should_collect.return_value = True


        result = benchmark(client.get, reverse("render-user-template"))

        assert result.status_code is 200
        assert len(django_elasticapm_client.events) > 0


@pytest.mark.django_db
@pytest.mark.parametrize('django_elasticapm_client', [{'_wait_to_first_send': 100}], indirect=True)
def test_perf_transaction_without_middleware(benchmark, django_elasticapm_client, client):
    django_elasticapm_client.instrumentation_store.get_all()
    with mock.patch("elasticapm.traces.TransactionsStore.should_collect") as should_collect:
        should_collect.return_value = False
        django_elasticapm_client.events = []
        for i in range(10):
            resp = client.get(reverse("render-user-template"))
            assert resp.status_code == 200

        assert len(django_elasticapm_client.events) == 0

        resp = benchmark(client.get, reverse("render-user-template"))
        assert resp.status_code == 200
        assert len(django_elasticapm_client.events) == 0
