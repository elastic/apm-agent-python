import os

import mock
from jinja2 import Environment, FileSystemLoader
from jinja2.environment import Template

import elasticapm.instrumentation.control
from tests.helpers import get_tempstoreclient
from tests.utils.compat import TestCase


class InstrumentJinja2Test(TestCase):
    def setUp(self):
        self.client = get_tempstoreclient()
        filedir = os.path.dirname(__file__)
        loader = FileSystemLoader(filedir)
        self.env = Environment(loader=loader)
        elasticapm.instrumentation.control.instrument()

    @mock.patch("elasticapm.traces.TransactionsStore.should_collect")
    def test_from_file(self, should_collect):
        should_collect.return_value = False
        self.client.begin_transaction("transaction.test")
        template = self.env.get_template('mytemplate.html')
        template.render()
        self.client.end_transaction("MyView")

        transactions = self.client.instrumentation_store.get_all()
        traces = transactions[0]['traces']

        expected_signatures = ['transaction', 'mytemplate.html']

        self.assertEqual(set([t['name'] for t in traces]),
                         set(expected_signatures))

        self.assertEqual(traces[0]['name'], 'mytemplate.html')
        self.assertEqual(traces[0]['type'], 'template.jinja2')

    def test_from_string(self):
        self.client.begin_transaction("transaction.test")
        template = Template("<html></html")
        template.render()
        self.client.end_transaction("test")

        transactions = self.client.instrumentation_store.get_all()
        traces = transactions[0]['traces']

        expected_signatures = ['transaction', '<template>']

        self.assertEqual(set([t['name'] for t in traces]),
                         set(expected_signatures))

        self.assertEqual(traces[0]['name'], '<template>')
        self.assertEqual(traces[0]['type'], 'template.jinja2')
