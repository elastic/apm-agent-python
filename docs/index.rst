Error logging: Python
=====================

.. csv-table::
	:class: page-info

	"Page updated: 23rd July 2013", ""

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
   Pylons <config/pylons>
   Pyramid <config/pyramid>
   Logging <config/logging>
   Logbook <config/logbook>
   WSGI Middle <config/wsgi>
   ZeroRPC <config/zerorpc>
   Other <config/other>