Flask
=================

.. csv-table::
  :class: page-info

  "Page updated: 4th April 2013", ""

Setup
-----

Using Opbeat with Flask requires the blinker library to be installed. This is most easily installed using pip:

.. code::
    :class: lang-bash

    $ pip install blinker

The first thing you'll need to do is to initialize opbeat under your application:

.. code::
    :class: lang-python

    from opbeat.contrib.flask import Opbeat
    opbeat = Opbeat(app, organization_id='<org-id>', app_id='<app-id>', secret_token='...')

If you don't specify the ``organization_id``, ``app_id`` and ``secret_token`` values, we will attempt to read it from your environment under the ``OPBEAT_ORGANIZATION_ID``, ``OPBEAT_APP_ID`` and ``OPBEAT_SECRET_TOKEN`` keys respectively.

Building applications on the fly? You can use opbeat's ``init_app`` hook:

.. code::
    :class: lang-python

    opbeat = Opbeat(organization_id='<org-id>', app_id='<app-id>', secret_token='...')

    def create_app():
        app = Flask(__name__)
        opbeat.init_app(app)
        return app

Settings
--------

Additional settings for the client can be configured using ``OPBEAT`` in your application's configuration:

.. code::
    :class: lang-python

    class MyConfig(object):
        OPBEAT = {
            'ORGANIZATION_ID': 'eb35323531c84b4589441cb6024c557a',
            'APP_ID': '6e43c2663d',
            'SECRET_TOKEN': '4f26b870afff47e586413a4113508abb56209989',
            'INCLUDE_PATHS': ['myproject']
        }

Usage
-----

Once you've configured the Opbeat application it will automatically capture uncaught exceptions within Flask. If you want to send additional events, a couple of shortcuts are provided on the Opbeat Flask middleware object.

Capture an arbitrary exception by calling ``captureException``:

.. code::
    :class: lang-python

    >>> try:
    >>>     1 / 0
    >>> except ZeroDivisionError:
    >>>     opbeat.captureException()

Log a generic message with ``captureMessage``:

.. code::
    :class: lang-python

    >>> opbeat.captureMessage('hello, world!')