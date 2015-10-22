import socket

import mock
import pytest

from opbeat.transport.base import TransportException
from opbeat.transport.http import HTTPTransport
from opbeat.utils import six
from opbeat.utils.compat import HTTPError, urlparse
from tests.utils.compat import TestCase


class TestHttpFailures(TestCase):
    @mock.patch('opbeat.transport.http.urlopen')
    def test_send(self, mock_urlopen):
        transport = HTTPTransport(urlparse.urlparse('http://localhost:9999'))
        mock_response = mock.Mock(
            info=lambda: {'Location': 'http://example.com/foo'}
        )
        mock_urlopen.return_value = mock_response
        url = transport.send('x', {})
        assert url == 'http://example.com/foo'
        assert mock_response.close.call_count == 1

    @mock.patch('opbeat.transport.http.urlopen')
    def test_timeout(self, mock_urlopen):
        transport = HTTPTransport(urlparse.urlparse('http://localhost:9999'))
        mock_urlopen.side_effect = socket.timeout()
        with pytest.raises(TransportException) as exc_info:
            transport.send('x', {})
        assert 'timeout' in str(exc_info.value)

    @mock.patch('opbeat.transport.http.urlopen')
    def test_http_error(self, mock_urlopen):
        url, status, message, body = (
            'http://localhost:9999', 418, "I'm a teapot", 'Nothing'
        )
        transport = HTTPTransport(urlparse.urlparse(url))
        mock_urlopen.side_effect = HTTPError(
            url, status, message, hdrs={}, fp=six.StringIO(body)
        )
        with pytest.raises(TransportException) as exc_info:
            transport.send('x', {})
        for val in (url, status, message, body):
            assert str(val) in str(exc_info.value)

    @mock.patch('opbeat.transport.http.urlopen')
    def test_generic_error(self, mock_urlopen):
        url, status, message, body = (
            'http://localhost:9999', 418, "I'm a teapot", 'Nothing'
        )
        transport = HTTPTransport(urlparse.urlparse(url))
        mock_urlopen.side_effect = Exception('Oopsie')
        with pytest.raises(TransportException) as exc_info:
            transport.send('x', {})
        assert 'Oopsie' in str(exc_info.value)
