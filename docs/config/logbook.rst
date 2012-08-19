Configuring ``logbook``
=======================

opbeat_python provides a `logbook <http://logbook.pocoo.org>`_ handler which will pipe
messages to Opbeat.

First you'll need to configure a handler::

    from opbeat_python.handlers.logbook import OpbeatHandler

    # Manually specify a client
    client = Client(...)
    handler = OpbeatHandler(client)

.. You can also automatically configure the default client with a DSN::

..     # Configure the default client
..     handler = SentryHandler('http://public:secret@example.com/1')

Finally, bind your handler to your context::

    from opbeat_python.handlers.logbook import OpbeatHandler

    client = Client(...)
    opbeat_handler = OpbeatHandler(client)
    with opbeat_handler.applicationbound():
        # everything logged here will go to sentry.
        ...
