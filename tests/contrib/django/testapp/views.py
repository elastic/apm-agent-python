from __future__ import absolute_import

import logging
import time

from django.contrib.auth.models import User
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, render, render_to_response

import elasticapm


class MyException(Exception):
    pass


class IgnoredException(Exception):
    skip_elasticapm = True


def no_error(request):
    resp = HttpResponse('')
    resp['My-Header'] = 'foo'
    return resp


def fake_login(request):
    return HttpResponse('')


def django_exc(request):
    return get_object_or_404(MyException, pk=1)


def raise_exc(request):
    raise MyException(request.GET.get('message', 'view exception'))


def raise_ioerror(request):
    raise IOError(request.GET.get('message', 'view exception'))


def decorated_raise_exc(request):
    return raise_exc(request)


def template_exc(request):
    return render_to_response('error.html')


def ignored_exception(request):
    raise IgnoredException()


def logging_request_exc(request):
    logger = logging.getLogger(__name__)
    try:
        raise Exception(request.GET.get('message', 'view exception'))
    except Exception as e:
        logger.error(e, exc_info=True, extra={'request': request})
    return HttpResponse('')


def logging_view(request):
    logger = logging.getLogger('logmiddleware')
    logger.info("Just loggin'")
    return HttpResponse('')


def render_template_view(request):
    def something_expensive():
        with elasticapm.capture_span("something_expensive", "code"):
            return [User(username='Ron'), User(username='Beni')]

    return render(request, "list_users.html",
                            {'users': something_expensive})


def render_jinja2_template(request):
    return render(request, "jinja2_template.html")


def render_user_view(request):
    def something_expensive():
        with elasticapm.capture_span("something_expensive", "code"):
            for i in range(100):
                users = list(User.objects.all())
        return users

    return render(request, "list_users.html",
                  {'users': something_expensive})


def streaming_view(request):
    def my_generator():
        for i in range(5):
            with elasticapm.capture_span('iter', 'code'):
                time.sleep(0.01)
                yield str(i)
    resp = StreamingHttpResponse(my_generator())
    return resp


def override_transaction_name_view(request):
    elasticapm.set_transaction_name('foo')
    elasticapm.set_transaction_result('okydoky')
    return HttpResponse()
