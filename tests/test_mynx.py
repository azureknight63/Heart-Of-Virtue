import os
import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path so absolute imports in src modules (e.g., `import genericng`) resolve.
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from src.npc import Mynx


class DummyPlayer:
    def __init__(self):
        self.combat_list = []
        self.combat_proximity = {}
        self.combat_list_allies = []


def test_mynx_non_combat():
    m = Mynx(name="MynxTest")
    p = DummyPlayer()
    # mynx should explicitly refuse combat
    assert not m.can_enter_combat()
    m.combat_engage(p)
    # ensure it didn't get added to player's combat collections
    assert m not in p.combat_list
    assert m.in_combat is False


def test_mynx_interact_plain_and_structured(capfd):
    m = Mynx(name="MynxTest")
    # plain (should print and return a string)
    text = m.talk(None, prompt="pet", structured=False)
    captured = capfd.readouterr()
    assert isinstance(text, str)
    # Either printed output or return value should contain expected phrase
    assert "leans into the hand" in (captured.out + text)

    # structured (should return a dict with expected fields)
    obj = m.talk(None, prompt="feed", structured=True)
    assert isinstance(obj, dict)
    assert obj.get("action") == "take_food"
    assert "tucks it into its tail-fur" in obj.get("description", "")


def test_mynx_pet_and_play_methods(capfd):
    m = Mynx(name="MynxTest")
    # pet (plain)
    text = m.pet(None, structured=False)
    captured = capfd.readouterr()
    assert isinstance(text, str)
    assert "leans into the hand" in (captured.out + text)

    # pet (structured)
    obj = m.pet(None, structured=True)
    assert isinstance(obj, dict)
    assert obj.get("action") == "groom"

    # play (plain) with an item name
    text2 = m.play(None, item="ribbon", structured=False)
    captured2 = capfd.readouterr()
    assert isinstance(text2, str)
    assert "bats the object" in (captured2.out + text2) or "pads forward" in (captured2.out + text2)

    # play (structured)
    obj2 = m.play(None, item="feather", structured=True)
    assert isinstance(obj2, dict)
    assert obj2.get("action") in ("play", "investigate")
