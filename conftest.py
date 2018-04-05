#!/usr/bin/env python
import sys
from os.path import abspath, dirname, join

from tests.fixtures import (elasticapm_client, instrument, not_so_random,
                            sending_elasticapm_client, validating_httpserver)
from tests.utils.compat import middleware_setting

try:
    from tests.contrib.django.fixtures import django_elasticapm_client, django_sending_elasticapm_client
except ImportError:
    pass

try:
    from tests.contrib.flask.fixtures import flask_app, flask_celery, flask_apm_client
except ImportError:
    pass

where_am_i = dirname(abspath(__file__))

BASE_TEMPLATE_DIR = join(where_am_i, 'tests', 'contrib', 'django', 'testapp',
                         'templates')

sys.path.insert(0, where_am_i)

# don't run tests of dependencies that land in "build" and "src"
collect_ignore = ['build', 'src']


try:
    from psycopg2cffi import compat
    compat.register()
except ImportError:
    pass


def pytest_configure(config):
    try:
        from django.conf import settings
    except ImportError:
        settings = None
    if settings is not None and not settings.configured:
        import django
        settings_dict = dict(
            DATABASES={
                'default': {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'NAME': 'elasticapm_tests.db',
                    'TEST_NAME': 'elasticapm_tests.db',
                    'TEST': {
                        'NAME': 'elasticapm_tests.db',
                    }
                },
            },
            TEST_DATABASE_NAME='elasticapm_tests.db',
            INSTALLED_APPS=[
                'django.contrib.auth',
                'django.contrib.admin',
                'django.contrib.sessions',
                'django.contrib.sites',
                'django.contrib.redirects',

                'django.contrib.contenttypes',

                'elasticapm.contrib.django',
                'tests.contrib.django.testapp',
            ],
            ROOT_URLCONF='tests.contrib.django.testapp.urls',
            DEBUG=False,
            SITE_ID=1,
            BROKER_HOST="localhost",
            BROKER_PORT=5672,
            BROKER_USER="guest",
            BROKER_PASSWORD="guest",
            BROKER_VHOST="/",
            CELERY_ALWAYS_EAGER=True,
            TEMPLATE_DEBUG=False,
            TEMPLATE_DIRS=[BASE_TEMPLATE_DIR],
            ALLOWED_HOSTS=['*'],
            TEMPLATES=[
                {
                    'BACKEND': 'django.template.backends.django.DjangoTemplates',
                    'DIRS': [BASE_TEMPLATE_DIR],
                    'OPTIONS': {
                        'context_processors': [
                            'django.contrib.auth.context_processors.auth',
                        ],
                        'loaders': [
                            'django.template.loaders.filesystem.Loader',
                        ],
                        'debug': False,
                    },
                },
            ]
        )
        settings_dict.update(**middleware_setting(django.VERSION, [
            'django.contrib.sessions.middleware.SessionMiddleware',
            'django.contrib.auth.middleware.AuthenticationMiddleware',
            'django.contrib.messages.middleware.MessageMiddleware',
        ]))
        settings.configure(**settings_dict)
        if hasattr(django, 'setup'):
            django.setup()
