from elasticapm.utils import get_url_dict
from elasticapm.utils.deprecation import deprecated


@deprecated("alternative")
def deprecated_function():
    pass


def test_deprecation():
    deprecated_function()


def test_get_url_dict():
    data = {
        'http://example.com': {
            'protocol': 'http:',
            'hostname': 'example.com',
            'pathname': '',
            'full': 'http://example.com',
        },
        'http://example.com:443': {
            'protocol': 'http:',
            'hostname': 'example.com',
            'port': '443',
            'pathname': '',
            'full': 'http://example.com:443',
        },
        'http://example.com:443/a/b/c': {
            'protocol': 'http:',
            'hostname': 'example.com',
            'port': '443',
            'pathname': '/a/b/c',
            'full': 'http://example.com:443/a/b/c',
        },
        'https://example.com:443/': {
            'protocol': 'https:',
            'hostname': 'example.com',
            'port': '443',
            'pathname': '/',
            'full': 'https://example.com:443/',
        },
        'https://example.com:443/a/b/c?de': {
            'protocol': 'https:',
            'hostname': 'example.com',
            'port': '443',
            'pathname': '/a/b/c',
            'search': '?de',
            'full': 'https://example.com:443/a/b/c?de',
        }
    }
    for url, expected in data.items():
        assert get_url_dict(url) == expected
