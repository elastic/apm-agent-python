Configuring ``WSGI`` Middleware
===============================

opbeat_python includes a simple to use WSGI middleware.

::

    from opbeat_python import Client
    from opbeat_python.middleware import Opbeat

    application = Opbeat(
        application,
        Client('http://public:secret@example.com/1')
    )

.. note:: Many frameworks will not propagate exceptions to the underlying WSGI middleware by default.
