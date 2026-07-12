import os
import sys
from pathlib import Path
from unittest.mock import patch

# Ensure the project's src directory is on sys.path so absolute imports in src modules (e.g., `import genericng`) resolve.
ROOT = Path(__file__).resolve().parent.parent


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
    """Test mynx plain and structured interactions with flexible LLM response matching.

    This test is resilient to LLM volatility by:
    - Checking for semantic equivalence rather than exact action matches
    - Accepting any action that could reasonably relate to feeding
    - Validating description content instead of exact phrasing
    - Allowing fallback responses from rate-limited LLM providers
    """
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
    assert isinstance(obj, dict), "Expected structured response to be a dict"
    assert "action" in obj, f"Expected 'action' key in response: {obj}"

    action = obj.get("action", "").lower()

    # Accept a wide range of semantically equivalent food-related actions
    # LLMs may interpret 'feed' differently: taking food, investigating food, consuming, etc.
    valid_feed_actions = {
        "take_food", "eat_food", "take", "eat", "consume", "accept", "grab",
        "snatch", "investigate_object", "inspect", "approach", "pounce", "investigate",
        "accept_food", "munch", "nibble", "sample", "receive", "grasp"
    }
    assert action in valid_feed_actions, (
        f"Expected action to be food/consumption related, got '{action}'. "
        f"Valid options: {valid_feed_actions}"
    )

    description = obj.get("description", "").lower()
    # Check for food-taking behavior (flexible to LLM variations)
    assert any(phrase in description for phrase in [
        "takes", "food", "hand", "eats", "consumes", "accepts", "snatches", "grabs",
        "tucks", "lifts", "paw", "grasp", "nudges", "morsel", "pounce", "investigate",
        "sniff", "smell", "munch", "nibble", "approach", "eye", "watch"
    ]), f"Expected food-related behavior in description: {obj.get('description', '')}"


def test_mynx_pet_and_play_methods(capfd):
    """Test mynx pet and play methods with flexible LLM response matching.

    This test is resilient to LLM volatility by:
    - Accepting a broader set of semantically equivalent actions
    - Checking for behavioral keywords rather than exact action names
    - Handling rate-limit fallbacks gracefully
    """
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
    assert isinstance(obj, dict), "Expected structured pet response to be a dict"
    assert "action" in obj, f"Expected 'action' key in pet response: {obj}"

    action = obj.get("action", "").lower()

    # Allow flexible action types for petting - LLMs might interpret as grooming, play, interaction, etc.
    valid_pet_actions = {
        "groom", "playful_tussle", "investigate", "play", "nuzzle", "stretch",
        "respond_affectionately", "bond", "relax", "purr", "accept", "enjoy",
        "lean", "rub", "cuddle", "sit", "close_eyes", "tail_wag", "content"
    }
    assert action in valid_pet_actions, (
        f"Expected action to be petting-related, got '{action}'. "
        f"Valid options: {valid_pet_actions}"
    )

    # play (plain) with an item name
    text2 = m.play(None, item="ribbon", structured=False)
    captured2 = capfd.readouterr()
    assert isinstance(text2, str)
    combined_output2 = captured2.out + text2
    # Check for playful behavior (flexible to LLM variations)
    assert any(phrase in combined_output2.lower() for phrase in [
        "bats", "plays", "pads forward", "chases", "pounces", "swats", "darts",
        "leaps", "bounces", "jumps", "paws", "twists", "spins", "runs", "pounce"
    ]), f"Expected playful behavior in: {combined_output2}"

    # play (structured)
    obj2 = m.play(None, item="feather", structured=True)
    assert isinstance(obj2, dict), "Expected structured play response to be a dict"
    assert "action" in obj2, f"Expected 'action' key in play response: {obj2}"

    action2 = obj2.get("action", "").lower()

    # Accept a wide range of play-related actions
    valid_play_actions = {
        "playful_tussle", "investigate", "play", "pounce", "chase", "bat",
        "swat", "leap", "jump", "bounce", "spin", "twist", "attack_toy",
        "interact", "attack", "chase_object", "toy_hunt", "hunt", "stalk"
    }
    assert action2 in valid_play_actions, (
        f"Expected action to be play-related, got '{action2}'. "
        f"Valid options: {valid_play_actions}"
    )


# ---------------------------------------------------------------------------
# Regression tests for GitHub issue #117: "Mynx LLM response contains error"
#
# Root cause: Mynx.talk() wraps interact_with_player() in try/except and
# degrades to a friendly fallback chitter on any unexpected exception, but
# Mynx.pet() and Mynx.play() did not have the same guard. Any exception
# raised inside interact_with_player() (e.g. a narration hiccup, a transient
# LLM/network error not already caught by the mixin's own internal
# try/excepts) would propagate uncaught out of pet()/play(), through
# GameService.interact_with_target()'s broad except handler, and surface to
# the player as a raw "Error executing action: <message>" string instead of
# degrading silently like talk() does. This matched the player report of
# repeatedly clicking Talk, then Pet, then Play and seeing a raw error.
# ---------------------------------------------------------------------------


def _raise_once_narrate(*args, **kwargs):
    """narrate() stand-in that raises on its *second* call.

    interact_with_player() narrates the player's action line first (e.g.
    "Jean plays with the mynx.") and then narrates the response text later.
    Raising on the second call simulates an unexpected failure deep inside
    the interaction pipeline without preventing the method from being
    entered at all.
    """
    _raise_once_narrate.calls += 1
    if _raise_once_narrate.calls >= 2:
        raise RuntimeError("simulated narration failure")


@pytest.mark.parametrize("method_name,call", [
    ("talk", lambda m, p: m.talk(p, prompt="talk")),
    ("pet", lambda m, p: m.pet(p)),
    ("play", lambda m, p: m.play(p)),
])
def test_mynx_interaction_degrades_gracefully_on_internal_error(method_name, call):
    """Talk, Pet, and Play must all recover silently from an unexpected
    exception raised inside interact_with_player(), rather than letting it
    bubble up to the caller (which the API layer would otherwise surface to
    the player as a raw error message).
    """
    m = Mynx(name="MynxTest")
    p = DummyPlayer()
    _raise_once_narrate.calls = 0

    with patch("src.npc._llm.narrate", side_effect=_raise_once_narrate):
        # Must not raise.
        result = call(m, p)

    # talk/pet/play all fall back to returning None on internal failure,
    # mirroring the pre-existing talk() behavior.
    assert result is None


def test_mynx_rapid_talk_pet_play_sequence_never_raises():
    """Simulates the exact player-reported sequence: clicking Talk, then
    Pet, then Play in quick succession. None of the three should ever let
    an internal exception escape to the caller, even if every call hits an
    unexpected internal failure.
    """
    m = Mynx(name="MynxTest")
    p = DummyPlayer()

    with patch("src.npc._llm.narrate", side_effect=RuntimeError("boom")):
        # None of these should raise — each should degrade to its fallback
        # "confused chitter" narration and return None.
        assert m.talk(p, prompt="talk") is None
        assert m.pet(p) is None
        assert m.play(p) is None


def test_mynx_pet_and_play_propagate_no_exception_types(capfd):
    """Sanity check without any forced failure: pet() and play() should
    behave normally (return a string or dict) when nothing goes wrong,
    confirming the new try/except doesn't change the happy path.
    """
    m = Mynx(name="MynxTest")
    p = DummyPlayer()

    text = m.pet(p, structured=False)
    assert isinstance(text, str)

    obj = m.play(p, item="ribbon", structured=True)
    assert isinstance(obj, dict)
