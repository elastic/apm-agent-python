# -*- coding: utf-8 -*-

from opbeat.transport.exceptions import InvalidScheme


class Transport(object):
    """
    All transport implementations need to subclass this class

    You must implement a send method and the compute_scope method.

    Please see the HTTPTransport class for an example of a
    compute_scope implementation.
    """
    async = False
    scheme = []

    def check_scheme(self, url):
        if url.scheme not in self.scheme:
            raise InvalidScheme()

    def send(self, data, headers):
        """
        You need to override this to do something with the actual
        data. Usually - this is sending to a server
        """
        raise NotImplementedError

    def compute_scope(self, url, scope):
        """
        You need to override this to compute the SENTRY specific
        additions to the variable scope.  See the HTTPTransport for an
        example.
        """
        raise NotImplementedError


class AsyncTransport(Transport):
    async = True

    def send_async(self, data, headers, success_callback=None, fail_callback=None):
        raise NotImplementedError
