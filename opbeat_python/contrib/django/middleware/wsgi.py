"""
opbeat_python.contrib.django.middleware.wsgi
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from opbeat_python.middleware import Sentry


class Sentry(Sentry):
    """
    Identical to the default WSGI middleware except that
    the client comes dynamically via ``get_client

    >>> from opbeat_python.contrib.django.middleware.wsgi import Sentry
    >>> application = Sentry(application)
    """
    def __init__(self, application):
        self.application = application

    @property
    def client(self):
        from opbeat_python.contrib.django.models import client
        return client
