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

import mock
import pytest

from elasticapm.utils import cgroup, compat


@pytest.mark.parametrize(
    "test_input,expected",
    [
        (
            "12:devices:/docker/051e2ee0bce99116029a13df4a9e943137f19f957f38ac02d6bad96f9b700f76",
            {"container": {"id": "051e2ee0bce99116029a13df4a9e943137f19f957f38ac02d6bad96f9b700f76"}},
        ),
        (
            "1:name=systemd:/system.slice/docker-cde7c2bab394630a42d73dc610b9c57415dced996106665d427f6d0566594411.scope",
            {"container": {"id": "cde7c2bab394630a42d73dc610b9c57415dced996106665d427f6d0566594411"}},
        ),
        (
            "1:name=systemd:/kubepods/besteffort/pode9b90526-f47d-11e8-b2a5-080027b9f4fb/15aa6e53-b09a-40c7-8558-c6c31e36c88a",
            {
                "container": {"id": "15aa6e53-b09a-40c7-8558-c6c31e36c88a"},
                "kubernetes": {"pod": {"uid": "e9b90526-f47d-11e8-b2a5-080027b9f4fb"}},
            },
        ),
        (
            "1:name=systemd:/kubepods.slice/kubepods-burstable.slice/kubepods-burstable-pod90d81341_92de_11e7_8cf2_507b9d4141fa.slice/crio-2227daf62df6694645fee5df53c1f91271546a9560e8600a525690ae252b7f63.scope",
            {
                "container": {"id": "2227daf62df6694645fee5df53c1f91271546a9560e8600a525690ae252b7f63"},
                "kubernetes": {"pod": {"uid": "90d81341-92de-11e7-8cf2-507b9d4141fa"}},
            },
        ),
        (
            "1:name=systemd:/system.slice/garden.service/garden/70eb4ce5-a065-4401-6990-88ed",
            {"container": {"id": "70eb4ce5-a065-4401-6990-88ed"}},
        ),
        (
            "12:pids:/kubepods/kubepods/besteffort/pod0e886e9a-3879-45f9-b44d-86ef9df03224/244a65edefdffe31685c42317c9054e71dc1193048cf9459e2a4dd35cbc1dba4",
            {
                "container": {"id": "244a65edefdffe31685c42317c9054e71dc1193048cf9459e2a4dd35cbc1dba4"},
                "kubernetes": {"pod": {"uid": "0e886e9a-3879-45f9-b44d-86ef9df03224"}},
            },
        ),
        (
            "10:cpuset:/kubepods/pod5eadac96-ab58-11ea-b82b-0242ac110009/7fe41c8a2d1da09420117894f11dd91f6c3a44dfeb7d125dc594bd53468861df",
            {
                "container": {"id": "7fe41c8a2d1da09420117894f11dd91f6c3a44dfeb7d125dc594bd53468861df"},
                "kubernetes": {"pod": {"uid": "5eadac96-ab58-11ea-b82b-0242ac110009"}},
            },
        ),
        (
            "9:freezer:/kubepods.slice/kubepods-pod22949dce_fd8b_11ea_8ede_98f2b32c645c.slice/docker-b15a5bdedd2e7645c3be271364324321b908314e4c77857bbfd32a041148c07f.scope",
            {
                "container": {"id": "b15a5bdedd2e7645c3be271364324321b908314e4c77857bbfd32a041148c07f"},
                "kubernetes": {"pod": {"uid": "22949dce-fd8b-11ea-8ede-98f2b32c645c"}},
            },
        ),
    ],
)
def test_cgroup_parsing(test_input, expected):
    f = compat.StringIO(test_input)
    result = cgroup.parse_cgroups(f)
    assert result == expected
