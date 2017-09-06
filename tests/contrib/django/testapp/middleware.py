try:
    from django.utils.deprecation import MiddlewareMixin
except ImportError:
    # no-op class for Django < 1.10
    class MiddlewareMixin(object):
        pass


class BrokenRequestMiddleware(MiddlewareMixin):
    def process_request(self, request):
        raise ImportError('request')


class BrokenResponseMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        raise ImportError('response')


class BrokenViewMiddleware(MiddlewareMixin):
    def process_view(self, request, func, args, kwargs):
        raise ImportError('view')


class MetricsNameOverrideMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        request._elasticapm_transaction_name = 'foobar'
        return response
