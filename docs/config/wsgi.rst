Configuring ``WSGI`` Middleware
===============================

opbeat includes a simple to use WSGI middleware.

::

    from opbeat import Client
    from opbeat.middleware import Opbeat

    application = Opbeat(
        application,
        Client(organization_id='<org-id>', app_id='<app-id>', secret_token='..')
    )

.. note:: Many frameworks will not propagate exceptions to the underlying WSGI middleware by default.
