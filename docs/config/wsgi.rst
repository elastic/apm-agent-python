Configuring ``WSGI`` Middleware
===============================

opbeat includes a simple to use WSGI middleware.

::

    from opbeat import Client
    from opbeat.middleware import Opbeat

    application = Opbeat(
        application,
        Client('http://public:secret@example.com/1')
    )

.. note:: Many frameworks will not propagate exceptions to the underlying WSGI middleware by default.
