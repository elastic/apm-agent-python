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
import os.path

from tests.utils.compat import middleware_setting

where_am_i = os.path.dirname(os.path.abspath(__file__))

BASE_TEMPLATE_DIR = os.path.join(where_am_i, "testapp", "templates")


def pytest_configure(config):
    try:
        from django.conf import settings
    except ImportError:
        settings = None
    if settings is not None and not settings.configured:
        import django

        settings_dict = dict(
            SECRET_KEY="42",
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": "elasticapm_tests.db",
                    "TEST_NAME": "elasticapm_tests.db",
                    "TEST": {"NAME": "elasticapm_tests.db"},
                }
            },
            TEST_DATABASE_NAME="elasticapm_tests.db",
            INSTALLED_APPS=[
                "django.contrib.auth",
                "django.contrib.admin",
                "django.contrib.sessions",
                "django.contrib.sites",
                "django.contrib.redirects",
                "django.contrib.contenttypes",
                "elasticapm.contrib.django",
                "tests.contrib.django.testapp",
            ],
            ROOT_URLCONF="tests.contrib.django.testapp.urls",
            DEBUG=False,
            SITE_ID=1,
            BROKER_HOST="localhost",
            BROKER_PORT=5672,
            BROKER_USER="guest",
            BROKER_PASSWORD="guest",
            BROKER_VHOST="/",
            CELERY_ALWAYS_EAGER=True,
            TEMPLATE_DEBUG=False,
            TEMPLATE_DIRS=[BASE_TEMPLATE_DIR],
            ALLOWED_HOSTS=["*"],
            TEMPLATES=[
                {
                    "BACKEND": "django.template.backends.django.DjangoTemplates",
                    "DIRS": [BASE_TEMPLATE_DIR],
                    "OPTIONS": {
                        "context_processors": ["django.contrib.auth.context_processors.auth"],
                        "loaders": ["django.template.loaders.filesystem.Loader"],
                        "debug": False,
                    },
                }
            ],
            ELASTIC_APM={
                "METRICS_INTERVAL": "0ms",
                "TRANSPORT_CLASS": "tests.fixtures.DummyTransport",
            },  # avoid autostarting the metrics collector thread
        )
        settings_dict.update(
            **middleware_setting(
                django.VERSION,
                [
                    "django.contrib.sessions.middleware.SessionMiddleware",
                    "django.contrib.auth.middleware.AuthenticationMiddleware",
                    "django.contrib.messages.middleware.MessageMiddleware",
                ],
            )
        )
        settings.configure(**settings_dict)
        if hasattr(django, "setup"):
            django.setup()
