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

import os
import platform
import subprocess
import sys

import pytest


@pytest.mark.skipif(platform.system() == "Windows", reason="Wrapper script unsupported on Windows")
@pytest.mark.skipif(
    sys.version_info >= (3, 12), reason="Test passes with a 5 second sleep in testapp.py"
)  # TODO py3.12
def test_wrapper_script_instrumentation():
    python = sys.executable

    elasticapm_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    pythonpath = os.environ.get("PYTHONPATH", "").split(";")
    pythonpath = [path for path in pythonpath if path != elasticapm_path]
    pythonpath.insert(0, elasticapm_path)
    os.environ["PYTHONPATH"] = os.path.pathsep.join(pythonpath)

    # Raises CalledProcessError if the return code is non-zero
    output = subprocess.check_output(
        [
            python,
            "-m",
            "elasticapm.instrumentation.wrapper",
            "python",  # Make sure we properly `which` the executable
            "tests/instrumentation/wrapper/testapp.py",
        ],
    )
    assert "SUCCESS" in output.decode("utf-8")
