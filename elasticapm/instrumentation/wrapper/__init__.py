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

import argparse
import os
import shutil

import elasticapm


def setup():
    parser = argparse.ArgumentParser(
        prog="elasticapm-run",
        description="""
        %(prog)s is a wrapper script for running python applications
        while automatically instrumenting with the Elastic APM python agent.
        """,
    )

    parser.add_argument(
        "--version", help="Print ElasticAPM version", action="version", version="%(prog)s " + elasticapm.VERSION
    )

    parser.add_argument(
        "--config",
        action="append",
        help="Config values to pass to ElasticAPM. Can be used multiple times. Ex: --config 'service_name=foo'",
    )
    parser.add_argument("app", help="Your python application")
    parser.add_argument("app_args", nargs=argparse.REMAINDER, help="Arguments for your python application", default=[])

    args = parser.parse_args()

    our_path = os.path.dirname(os.path.abspath(__file__))
    pythonpath = os.environ.get("PYTHONPATH", "").split(";")
    pythonpath = [path for path in pythonpath if path != our_path]
    pythonpath.insert(0, our_path)
    os.environ["PYTHONPATH"] = os.path.pathsep.join(pythonpath)

    for config in args.config or []:
        key, value = config.split("=", 1)
        os.environ["ELASTIC_APM_" + key.upper()] = value

    if args.app:
        app = shutil.which(args.app)
        os.execl(app, app, *args.app_args)
