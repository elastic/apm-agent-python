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

import logging
import time

from django.contrib.auth.models import User
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, render

import elasticapm
from elasticapm.utils import compat


class MyException(Exception):
    pass


class IgnoredException(Exception):
    skip_elasticapm = True


def no_error(request, id=None):
    resp = HttpResponse(compat.text_type(id))
    resp["My-Header"] = "foo"
    return resp


def fake_login(request):
    return HttpResponse("")


def django_exc(request):
    return get_object_or_404(MyException, pk=1)


def raise_exc(request):
    raise MyException(request.GET.get("message", "view exception"))


def raise_ioerror(request):
    raise IOError(request.GET.get("message", "view exception"))


def decorated_raise_exc(request):
    return raise_exc(request)


def template_exc(request):
    return render(request, "error.html")


def ignored_exception(request):
    raise IgnoredException()


def logging_request_exc(request):
    logger = logging.getLogger(__name__)
    try:
        raise Exception(request.GET.get("message", "view exception"))
    except Exception as e:
        logger.error(e, exc_info=True, extra={"request": request})
    return HttpResponse("")


def logging_view(request):
    logger = logging.getLogger("logmiddleware")
    logger.info("Just loggin'")
    return HttpResponse("")


def render_template_view(request):
    def something_expensive():
        with elasticapm.capture_span("something_expensive", "code"):
            return [User(username="Ron"), User(username="Beni")]

    return render(request, "list_users.html", {"users": something_expensive})


def render_jinja2_template(request):
    return render(request, "jinja2_template.html")


def render_user_view(request):
    def something_expensive():
        with elasticapm.capture_span("something_expensive", "code"):
            for i in range(100):
                users = list(User.objects.all())
        return users

    return render(request, "list_users.html", {"users": something_expensive})


def streaming_view(request):
    def my_generator():
        for i in range(5):
            with elasticapm.capture_span("iter", "code"):
                time.sleep(0.01)
                yield str(i)

    resp = StreamingHttpResponse(my_generator())
    return resp


def override_transaction_name_view(request):
    elasticapm.set_transaction_name("foo")
    elasticapm.set_transaction_result("okydoky")
    return HttpResponse()
