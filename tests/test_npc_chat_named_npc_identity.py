"""Issue #599: Jambo's portrait, Mara's dialogue.

``JamboHealsU`` has no authored chat config, so the mixin treated him as a
generic nomad and let a *generated* personality seed supply his name. The
generation prompt lists the story cast as reference proper nouns, the model
read the list as a name pool, and Jean opened a conversation with "Mara" under
Jambo's portrait. With the LLM off the same path labelled him "Ren".

Three layers, each pinned here:

* a named NPC (``_chat_keep_name``) keeps ``self.name`` whatever the seed says;
* a generated or restored seed may not borrow a name from the world-facts
  proper-noun list (one source of truth for the prompt and the validator);
* a generic nomad still wears its generated name -- the negative control.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

import ai.llm_client as llm_client
from ai.llm_client import NpcChatLLMAdapter
from src.npc import _chat_llm
from src.npc._eastern_descent import NomadCamper
from src.npc._merchants import JamboHealsU

from _npc_fixtures import ScriptedAdapter, chat_player


def _seed(given_name):
    return {
        "given_name": given_name,
        "voice": "dry and unhurried",
        "knowledge": ["herbs", "river fevers"],
        "attitude_to_strangers": "curious",
        "speech_sample": "Drink it slow or it comes back up.",
        "loquacity_base": 60,
    }


def _player():
    return chat_player(
        persist=True,
        universe=MagicMock(story={}, game_tick=10),
        charisma=10,
        combat_list_allies=[],
    )


@pytest.fixture
def world_facts_names():
    """The proper nouns the personality prompt shows the model, from disk.

    Read from the same JSON the prompt reads, so the test cannot drift from
    the data the way a hand-typed "Mara" would. Non-empty is asserted so a
    missing or renamed key fails loudly rather than making every assertion
    below vacuous.
    """
    with open(llm_client._NPC_CHAT_WORLD_FACTS_PATH, encoding="utf-8") as f:
        names = json.load(f)["allowed_proper_nouns"]
    assert names, "allowed_proper_nouns is empty; the tests below would be vacuous"
    assert "Mara" in names, "the #599 reproduction needs Mara on the list"
    return names


class TestNamedNpcKeepsItsName:
    """Layer A: ``_chat_keep_name`` hosts are called by ``self.name``."""

    def test_jambo_opts_in(self):
        assert JamboHealsU._chat_keep_name is True
        assert _chat_llm.ConversationalNPCMixin._chat_keep_name is False

    def test_jambo_stays_jambo_when_the_model_borrows_mara(self):
        """The reproduction: a seed naming him Mara never reaches the player."""
        jambo = JamboHealsU()
        jambo._chat_adapter = ScriptedAdapter(personality=_seed("Mara"))
        player = _player()

        payload = jambo.chat_open(player)

        assert payload["npc_name"] == "Jambo"
        block = jambo._build_character_block()
        assert block.startswith("You are Jambo, ")
        assert "Mara" not in block
        # The seed's traits survive; only the borrowed name is replaced.
        assert "dry and unhurried" in block
        assert jambo._chat_personality["given_name"] == "Jambo"
        persisted = player.npc_chat_histories["JamboHealsU_0"]["personality"]
        assert persisted["given_name"] == "Jambo"

    def test_jambo_stays_jambo_for_any_generated_name(self):
        """Not only reserved names: the seed's name is never his."""
        jambo = JamboHealsU()
        jambo._chat_adapter = ScriptedAdapter(personality=_seed("Tobin"))

        assert jambo.chat_open(_player())["npc_name"] == "Jambo"
        assert jambo._display_name() == "Jambo"
        assert "Tobin" not in jambo._build_character_block()

    def test_jambo_stays_jambo_with_the_llm_off(self):
        """The secondary defect: the authored fallback pool labelled him Ren."""
        jambo = JamboHealsU()
        jambo._chat_adapter = ScriptedAdapter(enabled=False)

        payload = jambo.chat_open(_player())

        assert payload["npc_name"] == "Jambo"
        assert jambo._chat_personality["given_name"] == "Jambo"
        assert jambo._build_character_block().startswith("You are Jambo, ")

    def test_character_block_describes_his_trade(self):
        jambo = JamboHealsU()
        jambo._chat_adapter = ScriptedAdapter(personality=_seed("Tobin"))
        jambo.chat_open(_player())

        block = jambo._build_character_block()
        assert "You are Jambo, " in block
        assert "merchant" in block.lower() or "healer" in block.lower()


class TestGeneratedNamesMayNotBorrowStoryNames:
    """Layer B: the validator and the prompt agree the list is not a pool."""

    def test_validate_personality_rejects_a_reserved_name(self, world_facts_names):
        for name in world_facts_names:
            assert NpcChatLLMAdapter._validate_personality(_seed(name)) is None, name

    def test_validate_personality_is_case_insensitive(self, world_facts_names):
        name = world_facts_names[0]
        assert NpcChatLLMAdapter._validate_personality(_seed(name.lower())) is None
        assert NpcChatLLMAdapter._validate_personality(_seed(name.upper())) is None
        assert NpcChatLLMAdapter._validate_personality(_seed(f"  {name} ")) is None

    def test_validate_personality_still_accepts_an_unreserved_name(self, world_facts_names):
        assert "Tobin" not in world_facts_names
        result = NpcChatLLMAdapter._validate_personality(_seed("Tobin"))
        assert result is not None
        assert result["given_name"] == "Tobin"

    def test_validate_personality_exempts_the_npcs_own_name(self):
        """A named NPC whose own name is on the list must still restore its seed."""
        reserved = next(iter(llm_client._reserved_given_names()))
        assert NpcChatLLMAdapter._validate_personality(_seed(reserved)) is None
        kept = NpcChatLLMAdapter._validate_personality(_seed(reserved), own_name=reserved)
        assert kept is not None and kept["given_name"] == reserved

    def test_reserved_names_come_from_the_world_facts_file(self, world_facts_names):
        reserved = llm_client._reserved_given_names()
        assert reserved == frozenset(n.lower() for n in world_facts_names)

    def test_restored_personality_rejects_a_reserved_name(self, world_facts_names):
        assert _chat_llm._validate_restored_personality(_seed("Mara")) is None
        assert _chat_llm._validate_restored_personality(_seed("Tobin")) is not None

    def test_generate_personality_drops_a_borrowed_name(self, monkeypatch):
        """End to end through the adapter: the model's Mara becomes ``None``,
        which is what sends the mixin to its authored pool."""
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        with patch.object(adapter, "_call_llm", return_value=json.dumps(_seed("Mara"))):
            assert adapter.generate_personality("JamboHealsU") is None

    def test_prompt_says_the_list_is_not_a_name_pool(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        with patch.object(adapter, "_call_llm", return_value=None) as call:
            adapter.generate_personality("Nomad")
        user_prompt = call.call_args[0][1]
        assert '"given_name"' in user_prompt
        assert "must not be any of" in user_prompt
        # The list itself is still there for the geography rule.
        assert "Mara" in user_prompt


class TestRestoredSeedsOnNamedNpcs:
    """Layer C: an existing save carrying the bad seed stops showing Mara."""

    def _persisted_player(self, given_name, **extra):
        player = _player()
        seed = _seed(given_name)
        seed.update(extra)
        player.npc_chat_histories = {
            "__meta__": {},
            "JamboHealsU_0": {
                "personality": seed,
                "loquacity_current": 40,
                "loquacity_max": 60,
                "loquacity_recovery": 2,
                "loquacity_scale": 15,
                "exchanges": [],
                "last_talked_tick": 0,
                "conversation_count": 1,
            },
        }
        return player

    def test_a_saved_mara_seed_does_not_surface_on_jambo(self):
        jambo = JamboHealsU()
        jambo._chat_adapter = ScriptedAdapter(enabled=False)
        player = self._persisted_player("Mara")

        payload = jambo.chat_open(player)

        assert payload["npc_name"] == "Jambo"
        assert "Mara" not in jambo._build_character_block()
        assert jambo._chat_personality["given_name"] == "Jambo"
        # The rewritten seed is what gets saved back, so the next load is clean.
        persisted = player.npc_chat_histories["JamboHealsU_0"]["personality"]
        assert persisted["given_name"] == "Jambo"

    def test_a_saved_ren_seed_is_reclaimed_but_keeps_its_traits(self):
        """Pre-fix LLM-off saves hold an authored pool entry; its voice is fine,
        its name is not."""
        jambo = JamboHealsU()
        jambo._chat_adapter = ScriptedAdapter(enabled=False)
        player = self._persisted_player("Ren", voice="sparse and direct")

        jambo.chat_open(player)

        assert jambo._display_name() == "Jambo"
        assert jambo._chat_personality["voice"] == "sparse and direct"

    def test_a_saved_seed_survives_the_npcs_own_name_being_reserved(self, monkeypatch):
        """If Jambo is ever added to world_facts, his own persisted seed must
        not be thrown away on every load."""
        monkeypatch.setattr(
            llm_client, "_RESERVED_GIVEN_NAMES",
            llm_client._reserved_given_names() | {"jambo"},
        )
        jambo = JamboHealsU()
        jambo._chat_adapter = ScriptedAdapter(enabled=False)
        player = self._persisted_player("Jambo", voice="a voice worth keeping")

        jambo.chat_open(player)

        assert jambo._display_name() == "Jambo"
        assert jambo._chat_personality["voice"] == "a voice worth keeping"


class TestGenericNomadsStillWearGeneratedNames:
    """Negative control: the behaviour #599 must not take away."""

    def test_generic_nomad_displays_its_generated_name(self):
        camper = NomadCamper()
        assert camper._chat_keep_name is False
        camper._chat_adapter = ScriptedAdapter(personality=_seed("Tobin"))
        player = _player()

        payload = camper.chat_open(player)

        assert payload["npc_name"] == "Tobin"
        assert camper._display_name() == "Tobin"
        assert camper._build_character_block().startswith("You are Tobin, a nomad.")
        persisted = player.npc_chat_histories["NomadCamper_0"]["personality"]
        assert persisted["given_name"] == "Tobin"

    def test_generic_nomad_with_the_llm_off_uses_the_authored_pool(self):
        camper = NomadCamper()
        camper._chat_adapter = ScriptedAdapter(enabled=False)

        payload = camper.chat_open(_player())

        pool_names = {p["given_name"] for p in _chat_llm._GENERIC_FALLBACKS}
        assert payload["npc_name"] in pool_names
