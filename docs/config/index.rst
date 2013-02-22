Configuration
=============

This document describes configuration options available to Opbeat.
For available framework integrations and modules, see the sidebar on the left.

.. container:: note

  Some integrations allow specifying these in a standard configuration, otherwise they are generally passed upon instantiation of the Opbeat client.

.. toctree::
   :maxdepth: 2
   :hidden:

   django
   flask
   pylons
   pyramid
   logging
   logbook
   wsgi
   zerorpc


Configuring the Client
----------------------

Settings are specified as part of the intialization of the client.

::

    from opbeat import Client

    # Read configuration from the environment
    client = Client()

    # Configure a client manually
    client = Client(
        organization_id='<org-id>',
        app_id='<org-id>',
        secret_token='<secret-token>',
    )

Client Arguments
----------------


The following are valid arguments which may be passed to the Opbeat client:

organization id
~~~~~~~~~~~~~~~~

Set this to your Opbeat organization ID.

::

    organization_id = 'fb9f9e31ea4f40d48855c603f15a2aa4'

app id
~~~~~~~~~~~~~~

Set this to your Opbeat app ID.

::

    app_id = 'fb9f9e31ea'

secret_token
~~~~~~~~~~~~~~~~~~

Set this to the secret key of the project.
You can find this information on the settings page of your project
at https://opbeat.com

::

    secret_token = '6e968b3d8ba240fcb50072ad9cba0810'

hostname
~~~~~~~~~~~~~~

This will override the ``hostname`` value for this installation. Defaults to ``socket.gethostname()``.

::

    hostname = 'opbeat_rocks_' + socket.gethostname()

exclude_paths
~~~~~~~~~~~~~

Extending this allow you to ignore module prefixes when we attempt to discover which function an error comes from (typically a view)

::

    exclude_paths = [
        'django',
        'opbeat',
        'lxml.objectify',
    ]

include_paths
~~~~~~~~~~~~~

For example, in Django this defaults to your list of ``INSTALLED_APPS``, and is used for drilling down where an exception is located

::

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

::

    list_max_length = 50

string_max_length
~~~~~~~~~~~~~~~~~

The maximum characters of a string that should be stored.

If a string is longer than the given length, it will be truncated down to the specified size.

::

    list_max_length = 200

auto_log_stacks
~~~~~~~~~~~~~~~

Should opbeat automatically log frame stacks (including locals) all calls as it would for exceptions.

::

    auto_log_stacks = True

timeout
~~~~~~~

If supported, the timeout value for sending messages to remote.

::

    timeout = 5

processors
~~~~~~~~~~

A list of processors to apply to events before sending them to the Opbeat server. Useful for sending
additional global state data or sanitizing data that you want to keep off of the server.

::

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
