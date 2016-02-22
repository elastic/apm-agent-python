from __future__ import absolute_import

import logging

from django.contrib.auth.models import User
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, render_to_response

from opbeat.traces import trace


def no_error(request):
    return HttpResponse('')


def fake_login(request):
    return HttpResponse('')


def django_exc(request):
    return get_object_or_404(Exception, pk=1)


def raise_exc(request):
    raise Exception(request.GET.get('message', 'view exception'))


def raise_ioerror(request):
    raise IOError(request.GET.get('message', 'view exception'))


def decorated_raise_exc(request):
    return raise_exc(request)


def template_exc(request):
    return render_to_response('error.html')


def logging_request_exc(request):
    logger = logging.getLogger(__name__)
    try:
        raise Exception(request.GET.get('message', 'view exception'))
    except Exception as e:
        logger.error(e, exc_info=True, extra={'request': request})
    return HttpResponse('')


def render_template_view(request):
    def something_expensive():
        with trace("something_expensive", "code"):
            return [User(username='Ron'), User(username='Beni')]

    return render(request, "list_users.html",
                            {'users': something_expensive})


def render_jinja2_template(request):
    return render(request, "jinja2_template.html")


def render_user_view(request):
    def something_expensive():
        with trace("something_expensive", "code"):
            for i in range(100):
                users = list(User.objects.all())
        return users

    return render(request, "list_users.html",
                  {'users': something_expensive})
