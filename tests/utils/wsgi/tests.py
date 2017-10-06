from __future__ import absolute_import

from elasticapm.utils.wsgi import get_environ, get_headers, get_host


def test_get_headers_tuple_as_key():
    result = dict(get_headers({
        ('a', 'tuple'): 'foo',
    }))
    assert result == {}


def test_get_headers_coerces_http_name():
    result = dict(get_headers({
        'HTTP_ACCEPT': 'text/plain',
    }))
    assert 'accept' in result
    assert result['accept'] == 'text/plain'


def test_get_headers_coerces_content_type():
    result = dict(get_headers({
        'CONTENT_TYPE': 'text/plain',
    }))
    assert 'content-type' in result
    assert result['content-type'] == 'text/plain'


def test_get_headers_coerces_content_length():
    result = dict(get_headers({
        'CONTENT_LENGTH': '134',
    }))
    assert 'content-length' in result
    assert result['content-length'] == '134'


def test_get_environ_has_remote_addr():
    result = dict(get_environ({'REMOTE_ADDR': '127.0.0.1'}))
    assert 'REMOTE_ADDR' in result
    assert result['REMOTE_ADDR'] == '127.0.0.1'


def test_get_environ_has_server_name():
    result = dict(get_environ({'SERVER_NAME': '127.0.0.1'}))
    assert 'SERVER_NAME' in result
    assert result['SERVER_NAME'] == '127.0.0.1'


def test_get_environ_has_server_port():
    result = dict(get_environ({'SERVER_PORT': 80}))
    assert 'SERVER_PORT' in result
    assert result['SERVER_PORT'] == 80


def test_get_environ_hides_wsgi_input():
    result = list(get_environ({'wsgi.input': 'foo'}))
    assert 'wsgi.input' not in result


def test_get_host_http_x_forwarded_host():
    result = get_host({'HTTP_X_FORWARDED_HOST': 'example.com'})
    assert result == 'example.com'


def test_get_host_http_host():
    result = get_host({'HTTP_HOST': 'example.com'})
    assert result == 'example.com'


def test_get_host_http_strips_port():
    result = get_host({
        'wsgi.url_scheme': 'http',
        'SERVER_NAME': 'example.com',
        'SERVER_PORT': '80',
    })
    assert result == 'example.com'


def test_get_host_https_strips_port():
    result = get_host({
        'wsgi.url_scheme': 'https',
        'SERVER_NAME': 'example.com',
        'SERVER_PORT': '443',
    })
    assert result == 'example.com'


def test_get_host_http_nonstandard_port():
    result = get_host({
        'wsgi.url_scheme': 'http',
        'SERVER_NAME': 'example.com',
        'SERVER_PORT': '81',
    })
    assert result == 'example.com:81'
