Configuring Pylons
==================

WSGI Middleware
---------------

A Pylons-specific middleware exists to enable easy configuration from settings:

::

    from opbeat.contrib.pylons import Opbeat

    application = Opbeat(application, config)

Configuration is handled via the opbeat namespace:

.. code-block:: ini

    [opbeat]
    organization_id=orgid
    app_id=gmwnmogdehmnmhau
    secret_token=asdasdasdasd
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

    [logger_opbeat]
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
    class = opbeat.handlers.logging.OpbeatHandler
    args = ('<organization_id>', '<app_id>', '<secret_token>')
    level = NOTSET
    formatter = generic

    [formatter_generic]
    format = %(asctime)s,%(msecs)03d %(levelname)-5.5s [%(name)s] %(message)s
    datefmt = %H:%M:%S

.. container:: note

    You may want to setup other loggers as well.


