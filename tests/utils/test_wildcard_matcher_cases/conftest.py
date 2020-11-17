#  BSD 3-Clause License
#
#  Copyright (c) 2020, Elasticsearch BV
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
import codecs
import json
import os

import pytest


def pytest_generate_tests(metafunc):
    if "pattern" in metafunc.fixturenames and "text" in metafunc.fixturenames:
        params = []
        json_cases = os.path.join(
            os.path.dirname(__file__), "..", "..", "upstream", "json-specs", "wildcard_matcher_tests.json"
        )
        with codecs.open(json_cases, encoding="utf8") as test_cases_file:
            test_cases = json.load(test_cases_file)
            for test_case, pattern_sets in test_cases.items():
                for pattern, texts in pattern_sets.items():
                    for text, should_ignore in texts.items():
                        params.append(
                            pytest.param(pattern, text, should_ignore, id="{}-{}-{}".format(test_case, pattern, text))
                        )
            metafunc.parametrize("pattern,text,should_match", params)
