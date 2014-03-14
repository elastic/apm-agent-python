Configuring Other stacks
=======================================

.. csv-table::
  :class: page-info

  "Page updated: 23rd July 2013", ""

Introduction
----------------------

This document describes configuration options available to Opbeat.
For available framework integrations and modules, see the sidebar on the left.

.. note::

  Some integrations allow specifying these in a standard configuration, otherwise they are generally passed upon instantiation of the Opbeat client.


Configuring the Client
----------------------

Settings are specified as part of the intialization of the client.

.. code::
  :class: language-python

    from opbeat import Client

    # Read configuration from the environment
    client = Client()

    # Configure a client manually
    client = Client(
        organization_id='<organization-id>',
        app_id='<app-id>',
        secret_token='<secret-token>',
    )

Client Arguments
----------------


The following are valid arguments which may be passed to the Opbeat client:

organization id
~~~~~~~~~~~~~~~~

Set this to your Opbeat organization ID.

.. code::
  :class: language-python

    organization_id = '<organization-id>'

app id
~~~~~~~~~~~~~~

Set this to your Opbeat app ID.

.. code::
  :class: language-python

    app_id = '<app-id>'

secret_token
~~~~~~~~~~~~~~~~~~

Set this to the secret key of the app.
You can find this information on the settings page of your app
at https://opbeat.com

.. code::
  :class: language-python

    secret_token = '<secret-token>'

hostname
~~~~~~~~~~~~~~

This will override the ``hostname`` value for this installation. Defaults to ``socket.gethostname()``.

.. code::
  :class: language-python

    hostname = 'opbeat_rocks_' + socket.gethostname()

exclude_paths
~~~~~~~~~~~~~

Extending this allow you to ignore module prefixes when we attempt to discover which function an error comes from (typically a view)

.. code::
  :class: language-python

    exclude_paths = [
        'django',
        'opbeat',
        'lxml.objectify',
    ]

include_paths
~~~~~~~~~~~~~

For example, in Django this defaults to your list of ``INSTALLED_APPS``, and is used for drilling down where an exception is located

.. code::
  :class: language-python

    include_paths = [
        'django',
        'opbeat',
        'lxml.objectify',
    ]

list_max_length
~~~~~~~~~~~~~~~

The maximum number of items a list-like container should store.

If an iterable is longer than the specified length, the left-most elements up to length will be kept.

.. note:: This affects sets as well, which are unordered.

.. code::
  :class: language-python

    list_max_length = 50

string_max_length
~~~~~~~~~~~~~~~~~

The maximum characters of a string that should be stored.

If a string is longer than the given length, it will be truncated down to the specified size.

.. code::
  :class: language-python

    list_max_length = 200

auto_log_stacks
~~~~~~~~~~~~~~~

Should opbeat automatically log frame stacks (including locals) all calls as it would for exceptions.

.. code::
  :class: language-python

    auto_log_stacks = True

timeout
~~~~~~~

If supported, the timeout value for sending messages to remote.

.. code::
  :class: language-python

    timeout = 5

processors
~~~~~~~~~~

A list of processors to apply to events before sending them to the Opbeat server. Useful for sending
additional global state data or sanitizing data that you want to keep off of the server.

.. code::
  :class: language-python

    processors = (
        'opbeat.processors.SanitizePasswordsProcessor',
    )

Sanitizing Data
---------------

Several processors are included with opbeat to assist in data sanitiziation. These are configured with the
``processors`` value.

.. data:: opbeat.processors.SanitizePasswordsProcessor

   Removes all keys which resemble ``password`` or ``secret`` within stacktrace contexts, and HTTP
   bits (such as cookies, POST data, the querystring, and environment).

.. data:: opbeat.processors.RemoveStackLocalsProcessor

   Removes all stacktrace context variables. This will cripple the functionality of Opbeat, as you'll only
   get raw tracebacks, but it will ensure no local scoped information is available to the server.

.. data:: opbeat.processors.RemovePostDataProcessor

   Removes the ``body`` of all HTTP data.


Usage
-----

.. autoclass:: opbeat.Client
   :members:
