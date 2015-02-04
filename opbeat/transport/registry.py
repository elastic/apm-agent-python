# -*- coding: utf-8 -*-

from opbeat.transport.exceptions import DuplicateScheme


class TransportRegistry(object):
    def __init__(self, transports=None):
        # setup a default list of senders
        self._schemes = {}
        self._transports = {}
        if transports:
            for transport in transports:
                for scheme in transport.scheme:
                    self.register_scheme(scheme, transport)

    def register_scheme(self, scheme, cls):
        """
        It is possible to inject new schemes at runtime
        """
        if scheme in self._schemes:
            raise DuplicateScheme(scheme)
        self._schemes[scheme] = cls

    def supported_scheme(self, scheme):
        return scheme in self._schemes

    def get_transport(self, parsed_url):
        scheme = parsed_url.scheme
        if scheme not in self._transports:
            self._transports[scheme] = self._schemes[scheme](parsed_url)
        return self._transports[parsed_url.scheme]

    def compute_scope(self, url, scope):
        """
        Compute a scope dictionary.  This may be overridden by custom
        transports
        """
        transport = self._schemes[url.scheme](url)
        return transport.compute_scope(url, scope)
