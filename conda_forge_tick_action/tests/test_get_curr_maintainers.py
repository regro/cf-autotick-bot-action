import subprocess
import pytest

from ..automerge import _get_curr_maintainers


def test_get_curr_maintainers():
    curr_maint = _get_curr_maintainers("cf-autotick-bot-test-package-feedstock")
    assert curr_maint == ["beckermr", "conda-forge/bot"]


def test_get_curr_maintainers_raises():
    with pytest.raises(AssertionError) as e:
        _get_curr_maintainers("blah")
    assert "is not a valid feedstock" in str(e.value)


def test_get_curr_maintainers_raises_clone():
    with pytest.raises(subprocess.CalledProcessError):
        _get_curr_maintainers("does-not-exist-feedstock")
