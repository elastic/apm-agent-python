Configuring ``logbook``
=======================

opbeat provides a `logbook <http://logbook.pocoo.org>`_ handler which will pipe
messages to Opbeat.

First you'll need to configure a handler::

    from opbeat.handlers.logbook import OpbeatHandler

    # Manually specify a client
    client = Client(...)
    handler = OpbeatHandler(client)

Finally, bind your handler to your context::

    from opbeat.handlers.logbook import OpbeatHandler

    client = Client(...)
    opbeat_handler = OpbeatHandler(client)
    with opbeat_handler.applicationbound():
        # everything logged here will go to sentry.
        ...
