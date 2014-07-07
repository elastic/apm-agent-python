try:
    from urllib2 import Request, urlopen
except ImportError:
    from urllib.request import Request, urlopen

from socket import socket, AF_INET, SOCK_DGRAM, error as socket_error

from opbeat.conf import defaults


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


class Transport(object):
    """
    All transport implementations need to subclass this class

    You must implement a send method and the compute_scope method.

    Please see the HTTPTransport class for an example of a
    compute_scope implementation.
    """
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


class HTTPTransport(Transport):

    scheme = ['http', 'https']

    def __init__(self, parsed_url):
        self.check_scheme(parsed_url)

        self._parsed_url = parsed_url
        self._url = parsed_url.geturl()

    def send(self, data, headers, timeout=None):
        """
        Sends a request to a remote webserver using HTTP POST.
        """
        req = Request(self._url, headers=headers)
        if timeout is None:
            timeout = defaults.TIMEOUT
        try:
            response = urlopen(req, data, timeout).read()
        except TypeError:
            response = urlopen(req, data).read()
        return response

    def compute_scope(self, url, scope):
        netloc = url.hostname
        if url.port and (url.scheme, url.port) not in \
                (('http', 80), ('https', 443)):
            netloc += ':%s' % url.port

        path_bits = url.path.rsplit('/', 1)
        if len(path_bits) > 1:
            path = path_bits[0]
        else:
            path = ''
        project = path_bits[-1]

        if not all([netloc, project, url.username, url.password]):
            raise ValueError('Invalid Opbeat DSN: %r' % url.geturl())

        server = '%s://%s%s/api/store/' % (url.scheme, netloc, path)
        scope.update({
            'SENTRY_SERVERS': [server],
            'SENTRY_PROJECT': project,
            'SENTRY_PUBLIC_KEY': url.username,
            'SENTRY_SECRET_KEY': url.password,
        })
        return scope


class TransportRegistry(object):
    def __init__(self):
        # setup a default list of senders
        self._schemes = {
                        # 'http': HTTPTransport,
                         'https': HTTPTransport,
                         # 'udp': UDPTransport
                         }
        self._transports = {}

    def register_scheme(self, scheme, cls):
        """
        It is possible to inject new schemes at runtime
        """
        if scheme in self._schemes:
            raise DuplicateScheme()

        # TODO (vng): verify the interface of the new class
        self._schemes[scheme] = cls

    def supported_scheme(self, scheme):
        return scheme in self._schemes

    def get_transport(self, parsed_url):
        return HTTPTransport(parsed_url)
        # if parsed_url.scheme not in self._transports:
        #     self._transports[parsed_url.scheme] = self._schemes[parsed_url.scheme](parsed_url)
        # return self._transports[parsed_url.scheme]

    def compute_scope(self, url, scope):
        """
        Compute a scope dictionary.  This may be overridden by custom
        transports
        """
        transport = self._schemes[url.scheme](url)
        return transport.compute_scope(url, scope)
