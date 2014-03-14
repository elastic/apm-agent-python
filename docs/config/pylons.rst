Configuring Pylons
==================

.. csv-table::
  :class: page-info

  "Page updated: 23rd July 2013", ""

WSGI Middleware
---------------

A Pylons-specific middleware exists to enable easy configuration from settings:

.. code::

    from opbeat.contrib.pylons import Opbeat

    application = Opbeat(application, config)

Configuration is handled via the opbeat namespace:

.. code::
    :class: language-ini

    [opbeat]
    organization_id=<organization-id>
    app_id=<app-id>
    secret_token=<secret-token>
    include_paths=my.package,my.other.package,
    exclude_paths=my.package.crud


Logger setup
------------

Add the following lines to your project's `.ini` file to setup `OpbeatHandler`:

.. code::
    :class: language-ini

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
    args = ('<organization-id>', '<app-id>', '<secret-token>')
    level = NOTSET
    formatter = generic

    [formatter_generic]
    format = %(asctime)s,%(msecs)03d %(levelname)-5.5s [%(name)s] %(message)s
    datefmt = %H:%M:%S

.. note::

    You may want to setup other loggers as well.


