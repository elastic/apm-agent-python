# -*- coding: utf-8 -*-


class InvalidScheme(ValueError):
    """
    Raised when a transport is constructed using a URI which is not
    handled by the transport
    """


class DuplicateScheme(Exception):
    """
    Raised when registering a handler for a particular scheme which
    is already registered
    """

    pass
