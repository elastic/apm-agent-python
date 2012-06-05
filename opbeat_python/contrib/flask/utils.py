import urlparse

from opbeat_python.utils.wsgi import get_headers, get_environ


def get_data_from_request(request):
    urlparts = urlparse.urlsplit(request.url)

    return {
        'sentry.interfaces.Http': {
            'url': '%s://%s%s' % (urlparts.scheme, urlparts.netloc, urlparts.path),
            'query_string': urlparts.query,
            'method': request.method,
            'data': request.form,
            'headers': dict(get_headers(request.environ)),
            'env': dict(get_environ(request.environ)),
        }
    }
