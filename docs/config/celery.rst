Configuring Celery
==================

Celery provides a hook for catching task failures, and opbeat can easily plug into that hook::

    from opbeat.contrib.celery import register_signal

    register_signal(client)

If you're using Django and ``djcelery`` exists in your ``INSTALLED_APPS``, we've already set this up for you.
