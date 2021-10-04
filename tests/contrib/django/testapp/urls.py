#  BSD 3-Clause License
#
#  Copyright (c) 2019, Elasticsearch BV
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  * Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from __future__ import absolute_import

import django
from django.conf import settings
from django.http import HttpResponse

from tests.contrib.django.testapp import views

try:
    from django.urls import re_path
except ImportError:
    # Django < 2
    from django.conf.urls import url as re_path


def handler500(request):
    if getattr(settings, "BREAK_THAT_500", False):
        raise ValueError("handler500")
    return HttpResponse("")


urlpatterns = (
    re_path(r"^render-heavy-template$", views.render_template_view, name="render-heavy-template"),
    re_path(r"^render-user-template$", views.render_user_view, name="render-user-template"),
    re_path(r"^no-error$", views.no_error, name="elasticapm-no-error"),
    re_path(r"^no-error-slash/$", views.no_error, name="elasticapm-no-error-slash"),
    re_path(r"^http-error/(?P<status>[0-9]{3})$", views.http_error, name="elasticapm-http-error"),
    re_path(r"^logging$", views.logging_view, name="elasticapm-logging"),
    re_path(r"^ignored-exception/$", views.ignored_exception, name="elasticapm-ignored-exception"),
    re_path(r"^fake-login$", views.fake_login, name="elasticapm-fake-login"),
    re_path(r"^trigger-500$", views.raise_exc, name="elasticapm-raise-exc"),
    re_path(r"^trigger-500-ioerror$", views.raise_ioerror, name="elasticapm-raise-ioerror"),
    re_path(r"^trigger-500-decorated$", views.decorated_raise_exc, name="elasticapm-raise-exc-decor"),
    re_path(r"^trigger-500-django$", views.django_exc, name="elasticapm-django-exc"),
    re_path(r"^trigger-500-template$", views.template_exc, name="elasticapm-template-exc"),
    re_path(r"^trigger-500-log-request$", views.logging_request_exc, name="elasticapm-log-request-exc"),
    re_path(r"^streaming$", views.streaming_view, name="elasticapm-streaming-view"),
    re_path(r"^name-override$", views.override_transaction_name_view, name="elasticapm-name-override"),
)


if django.VERSION >= (1, 8):
    urlpatterns += (re_path(r"^render-jinja2-template$", views.render_jinja2_template, name="render-jinja2-template"),)

if django.VERSION >= (2, 2):
    from django.urls import path

    urlpatterns += (
        path("route/<int:id>/", views.no_error, name="route-view"),
        path("", views.no_error, name="home-view"),
    )
