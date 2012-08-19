Configuring Pyramid
==================

PasteDeploy Filter
------------------

A filter factory for `PasteDeploy <http://pythonpaste.org/deploy/>`_ exists to allow easily inserting opbeat_python into a WSGI pipeline:

.. code-block:: ini

    [pipeline:main]
    pipeline =
        opbeat_python
        tm
        MyApp

    [filter:opbeat_python]
    use = egg:opbeat_python#paste_filter
    dsn = http://public:secret@example.com/1
    include_paths = my.package, my.other.package
    exclude_paths = my.package.crud

In the ``[filter:opbeat_python]`` section, you must specify the entry-point for opbeat_python with the ``use =`` key.  All other opbeat_python client parameters can be included in this section as well.

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
    class = opbeat_python.handlers.logging.OpbeatHandler
    args = ('http://public:secret@example.com/1',)
    level = WARNING
    formatter = generic

    [formatter_generic]
    format = %(asctime)s,%(msecs)03d %(levelname)-5.5s [%(name)s] %(message)s
    datefmt = %H:%M:%S

.. note:: You may want to setup other loggers as well.  See the `Pyramid Logging Documentation <http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/logging.html>`_ for more information.


