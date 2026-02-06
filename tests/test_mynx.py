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
    combined_output = captured.out + text
    # Check for affectionate petting behavior (flexible to LLM variations)
    assert "pet" in combined_output.lower(), f"Expected petting interaction in: {combined_output}"

    # structured (should return a dict with expected fields)
    obj = m.talk(None, prompt="feed", structured=True)
    assert isinstance(obj, dict)
    assert obj.get("action") == "take_food"
    description = obj.get("description", "").lower()
    # Check for food-taking behavior (flexible to LLM variations)
    assert any(phrase in description for phrase in [
        "takes", "food", "hand", "eats", "consumes", "accepts", "snatches", "grabs", "tucks", "lifts", "paw", "grasp", "nudges", "morsel"
    ]), f"Expected food-taking behavior in description: {obj.get('description', '')}"


def test_mynx_pet_and_play_methods(capfd):
    m = Mynx(name="MynxTest")
    # pet (plain)
    text = m.pet(None, structured=False)
    captured = capfd.readouterr()
    assert isinstance(text, str)
    combined_output = captured.out + text
    # Check for affectionate petting behavior (flexible to LLM variations)
    assert "pet" in combined_output.lower(), f"Expected petting interaction in: {combined_output}"

    # pet (structured)
    obj = m.pet(None, structured=True)
    assert isinstance(obj, dict)
    # Allow flexible action types for petting (LLM may choose different valid actions)
    assert obj.get("action") in ("groom", "playful_tussle", "investigate")

    # play (plain) with an item name
    text2 = m.play(None, item="ribbon", structured=False)
    captured2 = capfd.readouterr()
    assert isinstance(text2, str)
    combined_output2 = captured2.out + text2
    # Check for playful behavior (flexible to LLM variations)
    assert any(phrase in combined_output2.lower() for phrase in [
        "bats", "plays", "pads forward", "chases", "pounces", "swats", "darts"
    ]), f"Expected playful behavior in: {combined_output2}"

    # play (structured)
    obj2 = m.play(None, item="feather", structured=True)
    assert isinstance(obj2, dict)
    assert obj2.get("action") in ("playful_tussle", "investigate", "play")
