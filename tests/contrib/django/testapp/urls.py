from __future__ import absolute_import

import django
from django.conf import settings
from django.conf.urls import url
from django.http import HttpResponse

from tests.contrib.django.testapp import views


def handler500(request):
    if getattr(settings, 'BREAK_THAT_500', False):
        raise ValueError('handler500')
    return HttpResponse('')


urlpatterns = (
    url(r'^render-heavy-template$', views.render_template_view, name='render-heavy-template'),
    url(r'^render-user-template$', views.render_user_view, name='render-user-template'),
    url(r'^no-error$', views.no_error, name='elasticapm-no-error'),
    url(r'^no-error-slash/$', views.no_error, name='elasticapm-no-error-slash'),
    url(r'^logging$', views.logging_view, name='elasticapm-logging'),
    url(r'^ignored-exception/$', views.ignored_exception, name='elasticapm-ignored-exception'),
    url(r'^fake-login$', views.fake_login, name='elasticapm-fake-login'),
    url(r'^trigger-500$', views.raise_exc, name='elasticapm-raise-exc'),
    url(r'^trigger-500-ioerror$', views.raise_ioerror, name='elasticapm-raise-ioerror'),
    url(r'^trigger-500-decorated$', views.decorated_raise_exc, name='elasticapm-raise-exc-decor'),
    url(r'^trigger-500-django$', views.django_exc, name='elasticapm-django-exc'),
    url(r'^trigger-500-template$', views.template_exc, name='elasticapm-template-exc'),
    url(r'^trigger-500-log-request$', views.logging_request_exc, name='elasticapm-log-request-exc'),
)


if django.VERSION >= (1, 8):
    urlpatterns += url(r'^render-jinja2-template$', views.render_jinja2_template,
        name='render-jinja2-template'),
