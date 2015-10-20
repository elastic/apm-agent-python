import os

import mock
from jinja2 import Environment, FileSystemLoader
from jinja2.environment import Template

import opbeat.instrumentation.control
from tests.helpers import get_tempstoreclient
from tests.utils.compat import TestCase


class InstrumentJinja2Test(TestCase):
    def setUp(self):
        self.client = get_tempstoreclient()
        filedir = os.path.dirname(__file__)
        loader = FileSystemLoader(filedir)
        self.env = Environment(loader=loader)
        opbeat.instrumentation.control.instrument()

    @mock.patch("opbeat.traces.RequestsStore.should_collect")
    def test_from_file(self, should_collect):
        should_collect.return_value = False
        self.client.begin_transaction("transaction.test")
        template = self.env.get_template('mytemplate.html')
        template.render()
        self.client.end_transaction("MyView")

        transactions, traces = self.client.instrumentation_store.get_all()

        expected_signatures = ['transaction', 'mytemplate.html']

        self.assertEqual(set([t['signature'] for t in traces]),
                         set(expected_signatures))

        # Reorder according to the kinds list so we can just test them
        sig_dict = dict([(t['signature'], t) for t in traces])
        traces = [sig_dict[k] for k in expected_signatures]

        self.assertEqual(traces[1]['signature'], 'mytemplate.html')
        self.assertEqual(traces[1]['kind'], 'template.jinja2')
        self.assertEqual(traces[1]['transaction'], 'MyView')

    def test_from_string(self):
        self.client.begin_transaction("transaction.test")
        template = Template("<html></html")
        template.render()
        self.client.end_transaction("test")

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
