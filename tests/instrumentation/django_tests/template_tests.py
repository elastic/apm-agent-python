import pytest  # isort:skip
pytest.importorskip("django")  # isort:skip

from os.path import join

import django
from django.core.urlresolvers import reverse
from django.test import TestCase

import mock
import pytest

from conftest import BASE_TEMPLATE_DIR
from elasticapm.contrib.django.models import elasticapm, get_client

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


class TracesTest(TestCase):
    def setUp(self):
        self.elasticapm_client = get_client()
        elasticapm.instrumentation.control.instrument()

    @mock.patch("elasticapm.traces.TransactionsStore.should_collect")
    def test_template_rendering(self, should_collect):
        should_collect.return_value = False
        with self.settings(MIDDLEWARE_CLASSES=[
            'elasticapm.contrib.django.middleware.TracingMiddleware']):
            self.client.get(reverse('render-heavy-template'))
            self.client.get(reverse('render-heavy-template'))
            self.client.get(reverse('render-heavy-template'))

        transactions = self.elasticapm_client.instrumentation_store.get_all()

        self.assertEqual(len(transactions), 3)
        traces = transactions[0]['traces']
        self.assertEqual(len(traces), 3, [t['name'] for t in traces])

        kinds = ['transaction', 'code', 'template.django']
        self.assertEqual(set([t['type'] for t in traces]),
                         set(kinds))

        self.assertEqual(traces[0]['type'], 'code')
        self.assertEqual(traces[0]['name'], 'something_expensive')
        self.assertEqual(traces[0]['parent'], 1)

        self.assertEqual(traces[1]['type'], 'template.django')
        self.assertEqual(traces[1]['name'], 'list_users.html')
        self.assertEqual(traces[1]['parent'], 0)

        self.assertEqual(traces[2]['type'], 'transaction')
        self.assertEqual(traces[2]['name'], 'transaction')
        self.assertIsNone(traces[2]['parent'])

    @pytest.mark.skipif(django.VERSION < (1, 8),
                        reason='Jinja2 support introduced with Django 1.8')
    @mock.patch("elasticapm.traces.TransactionsStore.should_collect")
    def test_template_rendering_django18_jinja2(self, should_collect):
        should_collect.return_value = False
        with self.settings(MIDDLEWARE_CLASSES=[
                'elasticapm.contrib.django.middleware.TracingMiddleware'],
                TEMPLATES=TEMPLATES
            ):
            self.client.get(reverse('render-jinja2-template'))
            self.client.get(reverse('render-jinja2-template'))
            self.client.get(reverse('render-jinja2-template'))

        transactions = self.elasticapm_client.instrumentation_store.get_all()

        self.assertEqual(len(transactions), 3)
        traces = transactions[0]['traces']
        self.assertEqual(len(traces), 2, [t['name'] for t in traces])

        kinds = ['transaction', 'template.jinja2']
        self.assertEqual(set([t['type'] for t in traces]),
                         set(kinds))

        self.assertEqual(traces[0]['type'], 'template.jinja2')
        self.assertEqual(traces[0]['name'], 'jinja2_template.html')
        self.assertEqual(traces[0]['parent'], 0)

        self.assertEqual(traces[1]['type'], 'transaction')
        self.assertEqual(traces[1]['name'], 'transaction')
        self.assertIsNone(traces[1]['parent'])
