#!/usr/bin/env python
import logging
import sys
from os.path import dirname, abspath, join, splitext
from os import listdir
from django.conf import settings

where_am_i = dirname(abspath(__file__))

sys.path.insert(0, where_am_i)

# don't run tests of dependencies that land in "build" and "src"
collect_ignore = ['build', 'src']


def pytest_configure(config):
    if not settings.configured:
        settings.configure(
            DATABASE_ENGINE='sqlite3',
            DATABASES={
                'default': {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'TEST_NAME': 'opbeat_tests.db',
                    'NAME': 'opbeat_tests.db',
                },
            },
            # HACK: this fixes our threaded runserver remote tests
            DATABASE_NAME='opbeat_tests.db',
            TEST_DATABASE_NAME='opbeat_tests.db',
            INSTALLED_APPS=[
                'django.contrib.auth',
                'django.contrib.admin',
                'django.contrib.sessions',
                'django.contrib.sites',
                'django.contrib.redirects',

                'django.contrib.contenttypes',

                'djcelery',  # celery client

                'opbeat.contrib.django',
                'tests.contrib.django.testapp',
            ],
            ROOT_URLCONF='tests.contrib.django.urls',
            DEBUG=False,
            SITE_ID=1,
            BROKER_HOST="localhost",
            BROKER_PORT=5672,
            BROKER_USER="guest",
            BROKER_PASSWORD="guest",
            BROKER_VHOST="/",
            CELERY_ALWAYS_EAGER=True,
            TEMPLATE_DEBUG=True,
            TEMPLATE_DIRS=[join(where_am_i, 'tests', 'contrib', 'django', 'templates')],
            ALLOWED_HOSTS=['*'],
            MIDDLEWARE_CLASSES=[
                'django.contrib.sessions.middleware.SessionMiddleware',
                'django.contrib.auth.middleware.AuthenticationMiddleware',
                'django.contrib.messages.middleware.MessageMiddleware',
            ],
        )
        import django
        if hasattr(django, 'setup'):
            django.setup()
        import djcelery
        djcelery.setup_loader()
