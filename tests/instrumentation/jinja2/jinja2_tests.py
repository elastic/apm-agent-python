import os

from django.test import TestCase
from jinja2 import Environment, FileSystemLoader
from jinja2.environment import Template

from opbeat.contrib.django.models import get_client


class InstrumentJinja2Test(TestCase):
    def setUp(self):
        self.client = get_client()
        filedir = os.path.dirname(__file__)
        print filedir
        loader = FileSystemLoader(filedir)
        self.env = Environment(loader=loader)

    def test_from_file(self):
        self.client.begin_transaction()
        template = self.env.get_template('mytemplate.html')
        template.render()
        self.client.end_transaction(None, "test")

        transactions, traces = self.client.instrumentation_store.get_all()

        expected_signatures = ['transaction', 'mytemplate.html']

        self.assertEqual(set([t['signature'] for t in traces]),
                         set(expected_signatures))

        # Reorder according to the kinds list so we can just test them
        sig_dict = dict([(t['signature'], t) for t in traces])
        traces = [sig_dict[k] for k in expected_signatures]

        self.assertEqual(traces[1]['signature'], 'mytemplate.html')
        self.assertEqual(traces[1]['kind'], 'template.jinja2')
        self.assertEqual(traces[1]['transaction'], 'test')

    def test_from_string(self):
        self.client.begin_transaction()
        template = Template("<html></html")
        template.render()
        self.client.end_transaction(None, "test")

        transactions, traces = self.client.instrumentation_store.get_all()

        expected_signatures = ['transaction', '<template>']

        self.assertEqual(set([t['signature'] for t in traces]),
                         set(expected_signatures))

        # Reorder according to the kinds list so we can just test them
        sig_dict = dict([(t['signature'], t) for t in traces])
        traces = [sig_dict[k] for k in expected_signatures]

        self.assertEqual(traces[1]['signature'], '<template>')
        self.assertEqual(traces[1]['kind'], 'template.jinja2')
        self.assertEqual(traces[1]['transaction'], 'test')


