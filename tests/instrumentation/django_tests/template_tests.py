import pytest  # isort:skip
pytest.importorskip("django")  # isort:skip

from os.path import join

import django
from django.core.urlresolvers import reverse
from django.test import TestCase

import mock
import pytest

from conftest import BASE_TEMPLATE_DIR
from opbeat.contrib.django.models import get_client, opbeat

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
        self.opbeat = get_client()
        opbeat.instrumentation.control.instrument()

    @mock.patch("opbeat.traces.RequestsStore.should_collect")
    def test_template_rendering(self, should_collect):
        should_collect.return_value = False
        with self.settings(MIDDLEWARE_CLASSES=[
            'opbeat.contrib.django.middleware.OpbeatAPMMiddleware']):
            self.client.get(reverse('render-heavy-template'))
            self.client.get(reverse('render-heavy-template'))
            self.client.get(reverse('render-heavy-template'))

        transactions, traces = self.opbeat.instrumentation_store.get_all()

        self.assertEqual(len(transactions), 1)
        self.assertEqual(len(traces), 3, [t['signature'] for t in traces])

        kinds = ['transaction', 'code', 'template.django']
        self.assertEqual(set([t['kind'] for t in traces]),
                         set(kinds))

        # Reorder according to the kinds list so we can just test them
        kinds_dict = dict([(t['kind'], t) for t in traces])
        traces = [kinds_dict[k] for k in kinds]

        self.assertEqual(traces[0]['kind'], 'transaction')
        self.assertEqual(traces[0]['signature'], 'transaction')
        self.assertEqual(traces[0]['transaction'], 'GET tests.contrib.django.testapp.views.render_template_view')
        self.assertEqual(len(traces[0]['durations']), 3)
        self.assertEqual(len(traces[0]['parents']), 0)

        self.assertEqual(traces[1]['kind'], 'code')
        self.assertEqual(traces[1]['signature'], 'something_expensive')
        self.assertEqual(traces[1]['transaction'],
                         'GET tests.contrib.django.testapp.views.render_template_view')
        self.assertEqual(len(traces[1]['durations']), 3)
        self.assertEqual(traces[1]['parents'], ('transaction', 'list_users.html'))

        self.assertEqual(traces[2]['kind'], 'template.django')
        self.assertEqual(traces[2]['signature'], 'list_users.html')
        self.assertEqual(traces[2]['transaction'],
                         'GET tests.contrib.django.testapp.views.render_template_view')
        self.assertEqual(len(traces[2]['durations']), 3)
        self.assertEqual(traces[2]['parents'], ('transaction',))

    @pytest.mark.skipif(django.VERSION < (1, 8),
                        reason='Jinja2 support introduced with Django 1.8')
    @mock.patch("opbeat.traces.RequestsStore.should_collect")
    def test_template_rendering_django18_jinja2(self, should_collect):
        should_collect.return_value = False
        with self.settings(MIDDLEWARE_CLASSES=[
                'opbeat.contrib.django.middleware.OpbeatAPMMiddleware'],
                TEMPLATES=TEMPLATES
            ):
            self.client.get(reverse('render-jinja2-template'))
            self.client.get(reverse('render-jinja2-template'))
            self.client.get(reverse('render-jinja2-template'))

        transactions, traces = self.opbeat.instrumentation_store.get_all()

        self.assertEqual(len(transactions), 1)
        self.assertEqual(len(traces), 2, [t['signature'] for t in traces])

        kinds = ['transaction', 'template.jinja2']
        self.assertEqual(set([t['kind'] for t in traces]),
                         set(kinds))

        # Reorder according to the kinds list so we can just test them
        kinds_dict = dict([(t['kind'], t) for t in traces])
        traces = [kinds_dict[k] for k in kinds]

        self.assertEqual(traces[0]['kind'], 'transaction')
        self.assertEqual(traces[0]['signature'], 'transaction')
        self.assertEqual(traces[0]['transaction'],
                         'GET tests.contrib.django.testapp.views.render_jinja2_template')
        self.assertEqual(len(traces[0]['durations']), 3)
        self.assertEqual(len(traces[0]['parents']), 0)

        self.assertEqual(traces[1]['kind'], 'template.jinja2')
        self.assertEqual(traces[1]['signature'], 'jinja2_template.html')
        self.assertEqual(traces[1]['transaction'],
                         'GET tests.contrib.django.testapp.views.render_jinja2_template')
        self.assertEqual(len(traces[1]['durations']), 3)
        self.assertEqual(traces[1]['parents'], ('transaction',))
