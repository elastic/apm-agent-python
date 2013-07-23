Configuring Pyramid
===================

.. csv-table::
  :class: page-info

  "Page updated: 23rd July 2013", ""

PasteDeploy Filter
------------------

A filter factory for `PasteDeploy <http://pythonpaste.org/deploy/>`_ exists to allow easily inserting opbeat into a WSGI pipeline:

.. code-block:: ini

    [pipeline:main]
    pipeline =
        opbeat
        tm
        MyApp

    [filter:opbeat]
    use = egg:opbeat#paste_filter
    dsn = http://public:secret@example.com/1
    include_paths = my.package, my.other.package
    exclude_paths = my.package.crud

In the ``[filter:opbeat]`` section, you must specify the entry-point for opbeat with the ``use =`` key.  All other opbeat client parameters can be included in this section as well.

See the `Pyramid PasteDeploy Configuration Documentation <http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/paste.html>`_ for more information.

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
    args = ('http://public:secret@example.com/1',)
    level = WARNING
    formatter = generic

    [formatter_generic]
    format = %(asctime)s,%(msecs)03d %(levelname)-5.5s [%(name)s] %(message)s
    datefmt = %H:%M:%S

.. note::

    You may want to setup other loggers as well.  See the `Pyramid Logging Documentation <http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/logging.html>`_ for more information.


