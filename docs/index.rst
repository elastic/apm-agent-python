Error logging: Python
=====================

.. csv-table::
	:class: page-info

	"Page updated: 4th April 2013", ""

Introduction
------------
To send error logs to Opbeat, you must install an agent. 

This is the official Opbeat standalone Python agent. It is forked from `Raven <https://github.com/dcramer/raven>`_.

Requirements
------------
- pip
- simplejson (Only if you're using < Python 2.7)


Installation
------------

.. code::
	:class: lang-c

	# Install Opbeat
	$ pip install opbeat

Configuration
-------------


.. toctree::
   :maxdepth: 1

   Django <config/django>
   Flask <config/flask>
.. "`Pylons </docs/opbeat_python/docs/config/pylons>`_", ""
.. "`Pyramid </docs/opbeat_python/docs/config/pyramid>`_", ""
..	"`Logging </docs/opbeat_python/docs/config/logging>`_", ""
..	"`Logbook </docs/opbeat_python/docs/config/logbook>`_", ""
.. "`WSGI Middle </docs/opbeat_python/docs/config/wsgi>`_", ""
..	"`ZeroRPC </docs/opbeat_python/docs/config/zerorpc>`_", ""