Configuring Flask
=================

Setup
-----

The first thing you'll need to do is to initialize opbeat_python under your application::

    from opbeat_python.contrib.flask import Opbeat
    opbeat = Opbeat(app, project_id='921', api_key='...')

If you don't specify the ``project_id`` and ``api_key`` values, we will attempt to read it from your environment under the ``OPBEAT_PROJECT_ID`` and ``OPBEAT_API_KEY`` keys respectively.

Building applications on the fly? You can use opbeat_python's ``init_app`` hook::

    opbeat = Opbeat(project_id='921', api_key='...')

    def create_app():
        app = Flask(__name__)
        opbeat.init_app(app)
        return app

Settings
--------

Additional settings for the client can be configured using ``OPBEAT_<setting name>`` in your application's configuration::

    class MyConfig(object):
        OPBEAT_PROJECT_ID = '921'
        OPBEAT_API_KEY = '...'
        OPBEAT_INCLUDE_PATHS = ['myproject']

Usage
-----

Once you've configured the Opbeat application it will automatically capture uncaught exceptions within Flask. If you want to send additional events, a couple of shortcuts are provided on the Opbeat Flask middleware object.

Capture an arbitrary exception by calling ``captureException``::

    >>> try:
    >>>     1 / 0
    >>> except ZeroDivisionError:
    >>>     opbeat.captureException()

Log a generic message with ``captureMessage``::

    >>> opbeat.captureMessage('hello, world!')