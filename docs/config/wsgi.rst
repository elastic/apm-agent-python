Configuring ``WSGI`` Middleware
===============================

.. csv-table::
  :class: page-info

  "Page updated: 23rd July 2013", ""

opbeat includes a simple to use WSGI middleware.

::

    from opbeat import Client
    from opbeat.middleware import Opbeat

    application = Opbeat(
        application,
        Client(organization_id='<organization-id>', app_id='<app-id>', secret_token='<secret-token>')
    )

.. container:: note

    Many frameworks will not propagate exceptions to the underlying WSGI middleware by default.
