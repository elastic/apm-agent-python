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
"""
Framework integration for Tornado

Note that transaction creation is actually done in the tornado
instrumentation. This module only creates the client for later use by the
that instrumentation, and triggers the global instrumentation itself.
"""
import elasticapm
import tornado
from elasticapm import Client


class ElasticAPM:
    def __init__(self, app, client=None, **config):
        """
        Create the elasticapm Client object and store in the app for later
        use.

        ElasticAPM configuration is sent in via the **config kwargs, or
        optionally can be added to the application via the Application object
        (as a dictionary under the "ELASTIC_APM" key in the settings).
        """
        if "ELASTIC_APM" in app.settings and isinstance(app.settings["ELASTIC_APM"], dict):
            settings = app.settings["ELASTIC_APM"]
            settings.update(config)
            config = settings
        if not client:
            config.setdefault("framework_name", "tornado")
            config.setdefault("framework_version", tornado.version)
            client = Client(config)
        self.app = app
        self.client = client
        app.elasticapm_client = client

        # Don't instrument if debug=True in tornado, unless client.config.debug is True
        if (not self.app.settings.get("debug") or client.config.debug) and client.config.instrument:
            elasticapm.instrument()
