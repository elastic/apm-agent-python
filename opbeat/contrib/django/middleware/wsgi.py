"""
opbeat.contrib.django.middleware.wsgi
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from opbeat.middleware import Opbeat


class Opbeat(Opbeat):
    """
    Identical to the default WSGI middleware except that
    the client comes dynamically via ``get_client

    >>> from opbeat.contrib.django.middleware.wsgi import Opbeat
    >>> application = Opbeat(application)
    """
    def __init__(self, application):
        self.application = application

    @property
    def client(self):
        from opbeat.contrib.django.models import client
        return client
