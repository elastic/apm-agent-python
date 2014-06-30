from __future__ import absolute_import

import django
from django.conf import settings
if django.VERSION < (1, 3):
    from django.conf.urls.defaults import *  # Django 1.2
else:
    from django.conf.urls import *
from django.http import HttpResponse

def handler500(request):
    if getattr(settings, 'BREAK_THAT_500', False):
        raise ValueError('handler500')
    return HttpResponse('')

urlpatterns = patterns('',
    url(r'^no-error$', 'tests.contrib.django.views.no_error', name='opbeat-no-error'),
    url(r'^fake-login$', 'tests.contrib.django.views.fake_login', name='opbeat-fake-login'),
    url(r'^trigger-500$', 'tests.contrib.django.views.raise_exc', name='opbeat-raise-exc'),
    url(r'^trigger-500-ioerror$', 'tests.contrib.django.views.raise_ioerror', name='opbeat-raise-ioerror'),
    url(r'^trigger-500-decorated$', 'tests.contrib.django.views.decorated_raise_exc', name='opbeat-raise-exc-decor'),
    url(r'^trigger-500-django$', 'tests.contrib.django.views.django_exc', name='opbeat-django-exc'),
    url(r'^trigger-500-template$', 'tests.contrib.django.views.template_exc', name='opbeat-template-exc'),
    url(r'^trigger-500-log-request$', 'tests.contrib.django.views.logging_request_exc', name='opbeat-log-request-exc'),
)
