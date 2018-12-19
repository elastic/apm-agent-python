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
                "pod": {"uid": "e9b90526-f47d-11e8-b2a5-080027b9f4fb"},
            },
        ),
        (
            "1:name=systemd:/kubepods.slice/kubepods-burstable.slice/kubepods-burstable-pod90d81341_92de_11e7_8cf2_507b9d4141fa.slice/crio-2227daf62df6694645fee5df53c1f91271546a9560e8600a525690ae252b7f63.scope",
            {
                "container": {"id": "2227daf62df6694645fee5df53c1f91271546a9560e8600a525690ae252b7f63"},
                "pod": {"uid": "90d81341_92de_11e7_8cf2_507b9d4141fa"},
            },
        ),
    ],
)
def test_cgroup_parsing(test_input, expected):
    f = compat.StringIO(test_input)
    result = cgroup.parse_cgroups(f)
    assert result == expected
