import time

from mock import Mock

from opbeat.traces import RequestsStore, trace
from tests.utils.compat import TestCase


class RequestStoreTest(TestCase):
    def setUp(self):
        self.mock_get_frames = Mock()

        frames = [{'function': 'something_expensive',
                   'abs_path': '/var/parent-opbeat/opbeat_python/tests/contrib/django/testapp/views.py',
                   'lineno': 52, 'module': 'tests.contrib.django.testapp.views',
                   'filename': 'tests/contrib/django/testapp/views.py'},
                  {'function': '_resolve_lookup',
                   'abs_path': '/home/ron/.virtualenvs/opbeat_python/local/lib/python2.7/site-packages/django/template/base.py',
                   'lineno': 789, 'module': 'django.template.base',
                   'filename': 'django/template/base.py'},
                  {'function': 'resolve',
                   'abs_path': '/home/ron/.virtualenvs/opbeat_python/local/lib/python2.7/site-packages/django/template/base.py',
                   'lineno': 735, 'module': 'django.template.base',
                   'filename': 'django/template/base.py'},
                  {'function': 'resolve',
                   'abs_path': '/home/ron/.virtualenvs/opbeat_python/local/lib/python2.7/site-packages/django/template/base.py',
                   'lineno': 585, 'module': 'django.template.base',
                   'filename': 'django/template/base.py'}, {'lineno': 4,
                                                            'filename': u'/var/parent-opbeat/opbeat_python/tests/contrib/django/testapp/templates/list_fish.html'},
                  {'function': 'render',
                   'abs_path': '/home/ron/.virtualenvs/opbeat_python/local/lib/python2.7/site-packages/django/template/defaulttags.py',
                   'lineno': 4, 'module': 'django.template.defaulttags',
                   'filename': 'django/template/defaulttags.py'},
                  {'function': 'render_node',
                   'abs_path': '/home/ron/.virtualenvs/opbeat_python/local/lib/python2.7/site-packages/django/template/debug.py',
                   'lineno': 78, 'module': 'django.template.debug',
                   'filename': 'django/template/debug.py'},
                  {'function': 'render',
                   'abs_path': '/home/ron/.virtualenvs/opbeat_python/local/lib/python2.7/site-packages/django/template/base.py',
                   'lineno': 840, 'module': 'django.template.base',
                   'filename': 'django/template/base.py'},
                  {'function': 'instrumented_test_render',
                   'abs_path': '/home/ron/.virtualenvs/opbeat_python/local/lib/python2.7/site-packages/django/test/utils.py',
                   'lineno': 85, 'module': 'django.test.utils',
                   'filename': 'django/test/utils.py'}, {'function': 'render',
                                                         'abs_path': '/home/ron/.virtualenvs/opbeat_python/local/lib/python2.7/site-packages/django/template/base.py',
                                                         'lineno': 140,
                                                         'module': 'django.template.base',
                                                         'filename': 'django/template/base.py'},
                  {'function': 'rendered_content',
                   'abs_path': '/home/ron/.virtualenvs/opbeat_python/local/lib/python2.7/site-packages/django/template/response.py',
                   'lineno': 82, 'module': 'django.template.response',
                   'filename': 'django/template/response.py'},
                  {'function': 'render',
                   'abs_path': '/home/ron/.virtualenvs/opbeat_python/local/lib/python2.7/site-packages/django/template/response.py',
                   'lineno': 105, 'module': 'django.template.response',
                   'filename': 'django/template/response.py'},
                  {'function': 'get_response',
                   'abs_path': '/home/ron/.virtualenvs/opbeat_python/local/lib/python2.7/site-packages/django/core/handlers/base.py',
                   'lineno': 137, 'module': 'django.core.handlers.base',
                   'filename': 'django/core/handlers/base.py'},
                  {'function': '__call__',
                   'abs_path': '/home/ron/.virtualenvs/opbeat_python/local/lib/python2.7/site-packages/django/test/client.py',
                   'lineno': 109, 'module': 'django.test.client',
                   'filename': 'django/test/client.py'}, {'function': 'request',
                                                          'abs_path': '/home/ron/.virtualenvs/opbeat_python/local/lib/python2.7/site-packages/django/test/client.py',
                                                          'lineno': 426,
                                                          'module': 'django.test.client',
                                                          'filename': 'django/test/client.py'},
                  {'function': 'get',
                   'abs_path': '/home/ron/.virtualenvs/opbeat_python/local/lib/python2.7/site-packages/django/test/client.py',
                   'lineno': 280, 'module': 'django.test.client',
                   'filename': 'django/test/client.py'}, {'function': 'get',
                                                          'abs_path': '/home/ron/.virtualenvs/opbeat_python/local/lib/python2.7/site-packages/django/test/client.py',
                                                          'lineno': 473,
                                                          'module': 'django.test.client',
                                                          'filename': 'django/test/client.py'},
                  {'function': 'test_template_name_as_view',
                   'abs_path': '/var/parent-opbeat/opbeat_python/tests/contrib/django/django_tests.py',
                   'lineno': 710, 'module': 'tests.contrib.django.django_tests',
                   'filename': 'tests/contrib/django/django_tests.py'}]

        self.mock_get_frames.return_value = frames
        self.requests_store = RequestsStore(self.mock_get_frames, 99999)

    def test_lru_get_frames_cache(self):
        self.requests_store.transaction_start(None, "transaction.test")

        for i in range(10):
            with trace("bleh", "custom"):
                time.sleep(0.01)

        self.assertEqual(self.mock_get_frames.call_count, 1)

    def test_leaf_tracing(self):
        self.requests_store.transaction_start(None, "transaction.test")

        with trace("root", "custom"):
            with trace("child1-leaf", "custom", leaf=True):

                # These two traces should not show up
                with trace("ignored-child1", "custom", leaf=True):
                    time.sleep(0.01)

                with trace("ignored-child2", "custom", leaf=False):
                    time.sleep(0.01)

        self.requests_store.transaction_end(None, "transaction")

        transactions, traces = self.requests_store.get_all()

        self.assertEqual(len(traces), 3)

        signatures = ['transaction', 'root', 'child1-leaf']
        self.assertEqual(set([t['signature'] for t in traces]),
                         set(signatures))
