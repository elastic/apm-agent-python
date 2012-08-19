Configuring ``logging``
=======================

Opbeat supports the ability to directly tie into the :mod:`logging` module.  To
use it simply add :class:`OpbeatHandler` to your logger.

First you'll need to configure a handler::

    from opbeat_python.handlers.logging import OpbeatHandler

    # Manually specify a client
    client = Client(...)
    handler = OpbeatHandler(client)

.. You can also automatically configure the default client with a DSN::

..     # Configure the default client
..     handler = OpbeatHandler('http://public:secret@example.com/1')

Finally, call the :func:`setup_logging` helper function::

    from opbeat_python.conf import setup_logging

    setup_logging(handler)

Usage
~~~~~

A recommended pattern in logging is to simply reference the modules name for
each logger, so for example, you might at the top of your module define the
following::

    import logging
    logger = logging.getLogger(__name__)

You can also use the ``exc_info`` and ``extra={'stack': True}`` arguments on
your ``log`` methods. This will store the appropriate information and allow
Opbeat to render it based on that information::

    logger.error('There was some crazy error', exc_info=True, extra={
        'culprit': 'my.view.name',
    })

You may also pass additional information to be stored as meta information with
the event. As long as the key name is not reserved and not private (_foo) it
will be displayed on the Opbeat dashboard. To do this, pass it as ``data``
within your ``extra`` clause::

    logger.error('There was some crazy error', exc_info=True, extra={
        # Optionally you can pass additional arguments to specify request info
        'culprit': 'my.view.name',

        'data': {
            # You may specify any values here and Opbeat will log and output them
            'username': request.user.username,
        }
    })

.. note:: The ``url`` and ``view`` keys are used internally by Opbeat within the extra data.
.. note:: Any key (in ``data``) prefixed with ``_`` will not automatically output on the Opbeat details view.

Opbeat will intelligently group messages if you use proper string formatting. For example, the following messages would
be seen as the same message within Opbeat::

    logger.error('There was some %s error', 'crazy')
    logger.error('There was some %s error', 'fun')
    logger.error('There was some %s error', 1)

The :mod:`logging` integration also allows easy capture of
stack frames (and their locals) as if you were logging an exception. This can
be done automatically with the ``OPBEAT_AUTO_LOG_STACKS`` setting, as well as
by passing the ``stack`` boolean to ``extra``::

    logger.error('There was an error', extra={
        'stack': True,
    })

.. .. note::

..     Other languages that provide a logging package that is comparable to the
..     python :mod:`logging` package may define an Opbeat handler.  Check the
..     `Extending Opbeat
..     <http://sentry.readthedocs.org/en/latest/developer/client/index.html>`_
..     documentation.
