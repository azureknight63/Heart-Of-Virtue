import pytest

# TODO: Need to restructure project and imports, otherwise we'll eventually
# run into problems with the way $PYTHONPATH is set and imports are performed.
from universe import Universe


@pytest.mark.parametrize(
    "setting, expected_hidden, expected_hfactor",
    [("", False, 0), ("garbage", False, 0), ("h+0", True, 0), ("h+123", True, 123)],
)
def test_parse_hidden(setting: str, expected_hidden: bool, expected_hfactor: int):
    hidden, hfactor = Universe.parse_hidden(setting)

    assert hidden == expected_hidden
    assert hfactor == expected_hfactor
