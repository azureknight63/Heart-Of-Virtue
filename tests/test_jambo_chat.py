"""Jambo (JamboHealsU) must open the LLM Conversation dialog when talked to.

Regression coverage for the punchlist item: Jambo is a Merchant that historically
exposed only a static ``talk``; he must now carry ``ConversationalNPCMixin`` so the
frontend's Talk action opens NpcChatPanel (the LLM chat) instead of the bare
scripted line, while retaining his shop (buy/sell/trade) and his deterministic
fallback ``talk``.

The "red" state this guards against: a JamboHealsU with no mixin has no
``chat_open``/``chat_respond`` and serializes as ``llm_chat_enabled`` False, so the
the frontend never routes his Talk to the conversation dialog.
"""

from src.api.serializers.npc_serializer import NPCSerializer
from src.npc._chat_llm import ConversationalNPCMixin
from src.npc._merchants import JamboHealsU
from tests._npc_fixtures import ScriptedAdapter, chat_player


def _wired_jambo():
    """A real JamboHealsU instance wired for a live chat round (no provider).

    Hooks only the mixin's I/O seams — adapter, persistence, key, loquacity —
    and lets the real ``chat_open`` machinery (personality generation, system
    prompt, turn assembly, guard) run. ``_chat_config_path`` is left unset, so
    Jambo exercises the generic/story identity path, exactly as shipped.
    """
    jambo = JamboHealsU()
    adapter = ScriptedAdapter(npc_text="Jambo grins: the road west is long, friend.")
    jambo._get_adapter = lambda: adapter
    jambo._get_npc_key = lambda player: "JamboHealsU"
    jambo._compute_loquacity = lambda player: None
    jambo._get_chapter = lambda player: "1"
    jambo._load_history_from_persistence = lambda player: None
    jambo._save_exchange_to_persistence = lambda player, npc, jean, tick, chapter: None
    return jambo, adapter


def test_jambo_carries_conversational_mixin():
    jambo = JamboHealsU()
    assert isinstance(jambo, ConversationalNPCMixin)
    assert hasattr(jambo, "chat_open")
    assert hasattr(jambo, "chat_respond")


def test_jambo_talk_opens_llm_conversation_with_correct_key():
    jambo, _ = _wired_jambo()
    player = chat_player()
    result = jambo.chat_open(player)
    assert result.get("success") is True
    # The NPC key the route receives must be the class name, not the instance id.
    assert result.get("npc_key") == "JamboHealsU"
    assert result.get("npc_opening")
    # Three Jean options, QC'd and topped up by the real pipeline.
    assert len(result.get("jean_options", [])) == 3


def test_jambo_chat_respond_keeps_conversation_alive():
    jambo, _ = _wired_jambo()
    player = chat_player()
    opening = jambo.chat_open(player)
    assert opening.get("conversation_ended") is False
    reply = jambo.chat_respond(player, "Tell me about the road west.", "direct")
    assert reply.get("success") is True
    assert reply.get("npc_response")


def test_jambo_retains_shop_and_deterministic_talk_fallback():
    jambo = JamboHealsU()
    assert jambo.shop_name == "Jambo Heals U"
    player = chat_player()
    # Static talk must still run as the deterministic fallback (no error).
    jambo.talk(player)
    # Shop behavior unchanged.
    jambo.trade(player)


def test_jambo_serializer_reports_llm_chat_enabled_when_env_on(monkeypatch):
    monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "1")
    jambo = JamboHealsU()
    data = NPCSerializer.serialize(jambo)
    assert data.get("llm_chat_enabled") is True


def test_jambo_serializer_reports_llm_chat_disabled_when_env_off():
    jambo = JamboHealsU()
    data = NPCSerializer.serialize(jambo)
    # Has the mixin but the env gate is off, so the flag is False — the
    # frontend then falls back to the scripted talk (no 404 chat route).
    assert data.get("llm_chat_enabled") is False
