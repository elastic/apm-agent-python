import pytest  # isort:skip
pytest.importorskip("django")  # isort:skip

from os.path import join

import django
from django.test.utils import override_settings

import mock
import pytest

from conftest import BASE_TEMPLATE_DIR
from tests.utils.compat import middleware_setting

try:
    # Django 1.10+
    from django.urls import reverse
except ImportError:
    from django.core.urlresolvers import reverse



# Testing Django 1.8+ backends
TEMPLATES = (
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_TEMPLATE_DIR
        ],
    },
    {
        'BACKEND': 'django.template.backends.jinja2.Jinja2',
        'DIRS': [
            join(BASE_TEMPLATE_DIR, 'jinja2')
        ],
    },
)


@mock.patch("elasticapm.traces.TransactionsStore.should_collect")
def test_template_rendering(should_collect, django_elasticapm_client, client):
    should_collect.return_value = False
    with override_settings(**middleware_setting(django.VERSION,
                                            ['elasticapm.contrib.django.middleware.TracingMiddleware'])):
        client.get(reverse('render-heavy-template'))
        client.get(reverse('render-heavy-template'))
        client.get(reverse('render-heavy-template'))

    transactions = django_elasticapm_client.instrumentation_store.get_all()

    assert len(transactions) == 3
    traces = transactions[0]['traces']
    assert len(traces) == 2, [t['name'] for t in traces]

    kinds = ['code', 'template.django']
    assert set([t['type'] for t in traces]) == set(kinds)

    assert traces[0]['type'] == 'code'
    assert traces[0]['name'] == 'something_expensive'
    assert traces[0]['parent'] == 0

    assert traces[1]['type'] == 'template.django'
    assert traces[1]['name'] == 'list_users.html'
    assert traces[1]['parent'] is None


@pytest.mark.skipif(django.VERSION < (1, 8),
                    reason='Jinja2 support introduced with Django 1.8')
@mock.patch("elasticapm.traces.TransactionsStore.should_collect")
def test_template_rendering_django18_jinja2(should_collect, django_elasticapm_client, client):
    should_collect.return_value = False
    with override_settings(
            TEMPLATES=TEMPLATES,
            **middleware_setting(django.VERSION,
                                 ['elasticapm.contrib.django.middleware.TracingMiddleware'])
        ):
        client.get(reverse('render-jinja2-template'))
        client.get(reverse('render-jinja2-template'))
        client.get(reverse('render-jinja2-template'))

    transactions = django_elasticapm_client.instrumentation_store.get_all()

    assert len(transactions) == 3
    traces = transactions[0]['traces']
    assert len(traces) == 1, [t['name'] for t in traces]

    kinds = ['template.jinja2']
    assert set([t['type'] for t in traces]) == set(kinds)

    assert traces[0]['type'] == 'template.jinja2'
    assert traces[0]['name'] == 'jinja2_template.html'
    assert traces[0]['parent'] is None
