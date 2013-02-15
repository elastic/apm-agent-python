Install
=======

If you haven't already, start by downloading opbeat_python. The easiest way is with **pip**

.. code-block:: bash

	pip install opbeat_python -e git+git@github.com:opbeat/opbeat_python.git#egg=opbeat_python --upgrade

Requirements
------------

If you installed using pip or setuptools you shouldn't need to worry about requirements. Otherwise
you will need to install the following packages in your environment:

 - ``simplejson``

.. Upgrading from sentry.client
.. ----------------------------

.. If you're upgrading from the original ``sentry.client`` there are a few things you will need to note:

.. * SENTRY_SERVER is deprecated in favor of SENTRY_SERVERS (which is a list of URIs).
.. * ``sentry.client`` should be replaced with ``opbeat_python.contrib.django`` in ``INSTALLED_APPS``.
.. * ``sentry.client.celery`` should be replaced with ``opbeat_python.contrib.django.celery`` in ``INSTALLED_APPS``.
.. * ``sentry.handlers.SentryHandler`` should be replaced with ``opbeat_python.contrib.django.handlers.SentryHandler``
..   in your logging configuration.
.. * All Django specific middleware has been moved to ``opbeat_python.contrib.django.middleware``.
.. * The default Django client is now ``opbeat_python.contrib.django.DjangoClient``.
.. * The Django Celery client is now ``opbeat_python.contrib.django.celery.CeleryClient``.
