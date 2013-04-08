Django
======

.. csv-table::
  :class: page-info

  "Page updated: 4th April 2013", ""

Setup
-----

Using the Django integration is as simple as adding :mod:`opbeat.contrib.django` to your installed apps:

.. code::
    :class: lang-python wm

    INSTALLED_APPS = (
        'opbeat.contrib.django',
    )

Remember to add the following settings to settings.py:

.. code::
    :class: lang-python

    OPBEAT = {
        'ORGANIZATION_ID': '<organization-id>',
        'APP_ID': '<app-id>',
        'SECRET_TOKEN': '<secret-token>',
    }


Integration with logging
-------------------------------
To integrate with the standard library's logging module:

Django 1.3+
~~~~~~~~~~~~~~

.. code::
    :class: lang-json

    LOGGING = {
        'version': 1,
        'disable_existing_loggers': True,
        'root': {
            'level': 'WARNING',
            'handlers': ['opbeat'],
        },
        'formatters': {
            'verbose': {
                'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
            },
        },
        'handlers': {
            'opbeat': {
                'level': 'ERROR',
                'class': 'opbeat.contrib.django.handlers.OpbeatHandler',
            },
            'console': {
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
                'formatter': 'verbose'
            }
        },
        'loggers': {
            'django.db.backends': {
                'level': 'ERROR',
                'handlers': ['console'],
                'propagate': False,
            },
            'opbeat': {
                'level': 'DEBUG',
                'handlers': ['console'],
                'propagate': False,
            },
            'opbeat.errors': {
                'level': 'DEBUG',
                'handlers': ['console'],
                'propagate': False,
            },
        },
    }

Usage
~~~~~

Logging usage works the same way as it does outside of Django, with the
addition of an optional ``request`` key in the extra data:

.. code::
    :class: lang-python
    
    logger.error('There was some crazy error', exc_info=True, extra={
        # Optionally pass a request and we'll grab any information we can
        'request': request,
    })

404 Logging
-----------

In certain conditions you may wish to log 404 events to the Opbeat server. To
do this, you simply need to enable a Django middleware:

.. code::
    :class: lang-python

    MIDDLEWARE_CLASSES = MIDDLEWARE_CLASSES + (
      'opbeat.contrib.django.middleware.Opbeat404CatchMiddleware',
      ...,
    )

WSGI Middleware
---------------

If you are using a WSGI interface to serve your app, you can also apply a
middleware which will ensure that you catch errors even at the fundamental
level of your Django application:

.. code::
    :class: lang-python

    from opbeat.contrib.django.middleware.wsgi import Opbeat
    application = Opbeat(django.core.handlers.wsgi.WSGIHandler())

|

Additional Settings
-------------------

Opbeat client
~~~~~~~~~~~~~~

In some situations you may wish for a slightly different behavior to how Opbeat
communicates with your server. For this, opbeat allows you to specify a custom
client:

.. code::
    :class: lang-python

    OPBEAT = {
        'CLIENT': 'opbeat.contrib.django.DjangoClient',
        ...
    }

|

Caveats
-------

Error Handling Middleware
~~~~~~~~~~~~~~~~~~~~~~~~~

If you already have middleware in place that handles :func:`process_exception`
you will need to take extra care when using Opbeat.

For example, the following middleware would suppress Opbeat logging due to it
returning a response:

.. code::
    :class: lang-python wm

    class MyMiddleware(object):
        def process_exception(self, request, exception):
            return HttpResponse('foo')

To work around this, you can either disable your error handling middleware, or
add something like the following:

.. code::
    :class: lang-python

    from django.core.signals import got_request_exception
    class MyMiddleware(object):
        def process_exception(self, request, exception):
            # Make sure the exception signal is fired for Opbeat
            got_request_exception.send(sender=self, request=request)
            return HttpResponse('foo')

Note that this technique may break unit tests using the Django test client
(:class:`django.test.client.Client`) if a view under test generates a
:exc:`Http404 <django.http.Http404>` or :exc:`PermissionDenied` exception,
because the exceptions won't be translated into the expected 404 or 403
response codes.

|

Or, alternatively, you can just enable Opbeat responses:

.. code::
    :class: lang-python

    from opbeat.contrib.django.models import opbeat_exception_handler
    class MyMiddleware(object):
        def process_exception(self, request, exception):
            # Make sure the exception signal is fired for Opbeat
            opbeat_exception_handler(request=request)
            return HttpResponse('foo')
