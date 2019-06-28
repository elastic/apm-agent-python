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

import time

import mock

from elasticapm.utils.threading import IntervalTimer


def test_interval_timer():
    func = mock.Mock()
    timer = IntervalTimer(function=func, interval=0.1, args=(1,), kwargs={"a": "b"})
    timer.start()
    time.sleep(0.25)
    try:
        assert func.call_count == 2
        for call in func.call_args_list:
            assert call == ((1,), {"a": "b"})
    finally:
        timer.cancel()
    time.sleep(0.05)
    assert not timer.is_alive()


def test_interval_timer_interval_override():
    func = mock.Mock()
    func.return_value = 0.05
    timer = IntervalTimer(function=func, interval=0.1, evaluate_function_interval=True)
    timer.start()
    time.sleep(0.25)
    try:
        assert func.call_count in (3, 4)
    finally:
        timer.cancel()
    time.sleep(0.05)
    assert not timer.is_alive()


def test_interval_timer_interval_override_non_number():
    func = mock.Mock()
    func.return_value = "foo"
    timer = IntervalTimer(function=func, interval=0.1, evaluate_function_interval=True)
    timer.start()
    time.sleep(0.25)
    try:
        assert func.call_count == 2
    finally:
        timer.cancel()
    time.sleep(0.05)
    assert not timer.is_alive()
