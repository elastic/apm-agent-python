Configuring Pylons
==================

WSGI Middleware
---------------

A Pylons-specific middleware exists to enable easy configuration from settings:

::

    from opbeat_python.contrib.pylons import Opbeat

    application = Opbeat(application, config)

Configuration is handled via the opbeat namespace:

.. code-block:: ini

    [opbeat]
    project_id=gmwnmogdehmnmhau
    access_token=asdasdasdasd
    include_paths=my.package,my.other.package,
    exclude_paths=my.package.crud


Logger setup
------------

Add the following lines to your project's `.ini` file to setup `OpbeatHandler`:

.. code-block:: ini

    [loggers]
    keys = root, opbeat

    [handlers]
    keys = console, opbeat

    [formatters]
    keys = generic

    [logger_root]
    level = INFO
    handlers = console, opbeat

    [logger_sentry]
    level = WARN
    handlers = console
    qualname = opbeat.errors
    propagate = 0

    [handler_console]
    class = StreamHandler
    args = (sys.stderr,)
    level = NOTSET
    formatter = generic

    [handler_opbeat]
    class = opbeat_python.handlers.logging.OpbeatHandler
    args = (['http://sentry.local/api/store/'], 'KEY')
    level = NOTSET
    formatter = generic

    [formatter_generic]
    format = %(asctime)s,%(msecs)03d %(levelname)-5.5s [%(name)s] %(message)s
    datefmt = %H:%M:%S

.. note:: You may want to setup other loggers as well.


