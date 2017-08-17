import time

from mock import Mock

from elasticapm.traces import TransactionsStore, get_transaction, trace
from tests.utils.compat import TestCase


class RequestStoreTest(TestCase):
    def setUp(self):
        self.mock_get_frames = Mock()

        frames = [{'function': 'something_expensive',
                   'abs_path': '/var/parent-elasticapm/elasticapm/tests/contrib/django/testapp/views.py',
                   'lineno': 52, 'module': 'tests.contrib.django.testapp.views',
                   'filename': 'tests/contrib/django/testapp/views.py'},
                  {'function': '_resolve_lookup',
                   'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/template/base.py',
                   'lineno': 789, 'module': 'django.template.base',
                   'filename': 'django/template/base.py'},
                  {'function': 'resolve',
                   'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/template/base.py',
                   'lineno': 735, 'module': 'django.template.base',
                   'filename': 'django/template/base.py'},
                  {'function': 'resolve',
                   'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/template/base.py',
                   'lineno': 585, 'module': 'django.template.base',
                   'filename': 'django/template/base.py'}, {'lineno': 4,
                                                            'filename': u'/var/parent-elasticapm/elasticapm/tests/contrib/django/testapp/templates/list_fish.html'},
                  {'function': 'render',
                   'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/template/defaulttags.py',
                   'lineno': 4, 'module': 'django.template.defaulttags',
                   'filename': 'django/template/defaulttags.py'},
                  {'function': 'render_node',
                   'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/template/debug.py',
                   'lineno': 78, 'module': 'django.template.debug',
                   'filename': 'django/template/debug.py'},
                  {'function': 'render',
                   'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/template/base.py',
                   'lineno': 840, 'module': 'django.template.base',
                   'filename': 'django/template/base.py'},
                  {'function': 'instrumented_test_render',
                   'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/test/utils.py',
                   'lineno': 85, 'module': 'django.test.utils',
                   'filename': 'django/test/utils.py'}, {'function': 'render',
                                                         'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/template/base.py',
                                                         'lineno': 140,
                                                         'module': 'django.template.base',
                                                         'filename': 'django/template/base.py'},
                  {'function': 'rendered_content',
                   'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/template/response.py',
                   'lineno': 82, 'module': 'django.template.response',
                   'filename': 'django/template/response.py'},
                  {'function': 'render',
                   'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/template/response.py',
                   'lineno': 105, 'module': 'django.template.response',
                   'filename': 'django/template/response.py'},
                  {'function': 'get_response',
                   'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/core/handlers/base.py',
                   'lineno': 137, 'module': 'django.core.handlers.base',
                   'filename': 'django/core/handlers/base.py'},
                  {'function': '__call__',
                   'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/test/client.py',
                   'lineno': 109, 'module': 'django.test.client',
                   'filename': 'django/test/client.py'}, {'function': 'request',
                                                          'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/test/client.py',
                                                          'lineno': 426,
                                                          'module': 'django.test.client',
                                                          'filename': 'django/test/client.py'},
                  {'function': 'get',
                   'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/test/client.py',
                   'lineno': 280, 'module': 'django.test.client',
                   'filename': 'django/test/client.py'}, {'function': 'get',
                                                          'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/test/client.py',
                                                          'lineno': 473,
                                                          'module': 'django.test.client',
                                                          'filename': 'django/test/client.py'},
                  {'function': 'test_template_name_as_view',
                   'abs_path': '/var/parent-elasticapm/elasticapm/tests/contrib/django/django_tests.py',
                   'lineno': 710, 'module': 'tests.contrib.django.django_tests',
                   'filename': 'tests/contrib/django/django_tests.py'}]

        self.mock_get_frames.return_value = frames
        self.requests_store = TransactionsStore(self.mock_get_frames, 99999)

    def test_lru_get_frames_cache(self):
        self.requests_store.begin_transaction("transaction.test")

        for i in range(10):
            with trace("bleh", "custom"):
                time.sleep(0.01)

        self.assertEqual(self.mock_get_frames.call_count, 10)

    def test_leaf_tracing(self):
        self.requests_store.begin_transaction("transaction.test")

        with trace("root", "custom"):
            with trace("child1-leaf", "custom", leaf=True):

                # These two traces should not show up
                with trace("ignored-child1", "custom", leaf=True):
                    time.sleep(0.01)

                with trace("ignored-child2", "custom", leaf=False):
                    time.sleep(0.01)

        self.requests_store.end_transaction(None, "transaction")

        transactions = self.requests_store.get_all()
        traces = transactions[0]['traces']

        self.assertEqual(len(traces), 3)

        signatures = ['transaction', 'root', 'child1-leaf']
        self.assertEqual(set([t['name'] for t in traces]),
                         set(signatures))


def test_get_transaction():
    requests_store = TransactionsStore(lambda: [], 99999)
    t = requests_store.begin_transaction("test")
    assert t == get_transaction()


def test_get_transaction_clear():
    requests_store = TransactionsStore(lambda: [], 99999)
    t = requests_store.begin_transaction("test")
    assert t == get_transaction(clear=True)
    assert get_transaction() is None
