#  BSD 3-Clause License
#
#  Copyright (c) 2022, Elasticsearch BV
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

import logging

from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule


class FlaskInstrumentation(AbstractInstrumentedModule):
    name = "flask"

    instrument_list = [("flask", "Flask.__init__")]

    creates_transactions = True

    def call(self, module, method, wrapped, instance, args, kwargs):
        from elasticapm.contrib.flask import ElasticAPM

        wrapped(*args, **kwargs)
        client = ElasticAPM(instance)
        instance.elasticapm_client = client
        self.instance = instance

    def uninstrument(self):
        """
        This is mostly here for testing. If we want to support live
        instrumenting and uninstrumenting, we'll need to also extend the
        `instrument()` method to add the signals removed here.
        """
        super().uninstrument()

        # Only remove signals during uninstrument if we auto-instrumented
        flask_app = getattr(self, "instance", None)
        if flask_app:
            client = flask_app.elasticapm_client
            from flask import signals

            signals.request_started.disconnect(client.request_started)
            signals.request_finished.disconnect(client.request_finished)
            # remove logging handler if it was added
            logger = logging.getLogger()
            for handler in list(logger.handlers):
                if getattr(handler, "client", None) is client.client:
                    logger.removeHandler(handler)
            self.instance = None
