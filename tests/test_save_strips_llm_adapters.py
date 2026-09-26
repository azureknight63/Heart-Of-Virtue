"""A chatted-with NPC must still save.

The LLM mixins cache their adapter on the NPC instance (``_chat_adapter`` on
ConversationalNPCMixin, ``_llm_adapter`` on MynxLLMMixin). Those NPCs are part
of the world a save pickles, and an adapter holds a live HTTPS client: on
production (2026-09-25) every save after one NPC chat failed with
``TypeError: cannot pickle 'GreenSSLContext' object``. A plain ``ssl.SSLContext``
fails the same way, which is what these tests hold.

The adapter's "failed" marker is a bare ``object()`` sentinel, so a pickled one
comes back as a *different* object and ``is self._ADAPTER_FAILED`` no longer
matches -- the loaded NPC would treat it as a live adapter. Both cases reset to
None, which makes the NPC rebuild (or re-refuse) on its next chat.
"""
import pickle
import re
import ssl
from pathlib import Path

import pytest

from src.npc import Mara, Mynx
from src.npc._chat_llm import ConversationalNPCMixin
from src.npc._llm import MynxLLMMixin
from src.secure_pickle import serialize_for_save

NPC_DIR = Path(__file__).resolve().parent.parent / "src" / "npc"


class _AdapterHoldingAConnection:
    """Stands in for NpcChatLLMAdapter / MynxLLMAdapter: what makes them
    unpicklable is the HTTPS client's SSL context."""

    def __init__(self):
        self.ssl_context = ssl.create_default_context()


def _round_trip(obj):
    return pickle.loads(pickle.dumps(obj, pickle.HIGHEST_PROTOCOL))


CASES = [
    pytest.param(Mara, {}, "_chat_adapter", id="Mara._chat_adapter"),
    pytest.param(Mynx, {"name": "MynxTest"}, "_llm_adapter", id="Mynx._llm_adapter"),
]


@pytest.mark.parametrize("npc_class, kwargs, attr", CASES)
def test_an_npc_holding_a_live_adapter_saves_and_loads_without_it(npc_class, kwargs, attr):
    npc = npc_class(**kwargs)
    setattr(npc, attr, _AdapterHoldingAConnection())

    serialize_for_save(npc)  # raised TypeError: cannot pickle 'SSLContext' object

    loaded = _round_trip(npc)
    assert getattr(loaded, attr) is None
    # The live NPC keeps its adapter: only the saved copy drops it.
    assert isinstance(getattr(npc, attr), _AdapterHoldingAConnection)


@pytest.mark.parametrize("npc_class, kwargs, attr", CASES)
def test_the_failed_sentinel_does_not_come_back_as_an_imposter(npc_class, kwargs, attr):
    npc = npc_class(**kwargs)
    setattr(npc, attr, npc_class._ADAPTER_FAILED)

    loaded = _round_trip(npc)

    assert getattr(loaded, attr) is None


def test_every_cached_adapter_attribute_is_declared_unsaved():
    """Population from the source: every attribute some NPC mixin assigns the
    ``_ADAPTER_FAILED`` sentinel to is an adapter cache, and must be declared."""
    cached = set()
    for path in NPC_DIR.glob("*.py"):
        cached |= set(re.findall(r"self\.(\w+)\s*=\s*self\._ADAPTER_FAILED\b", path.read_text(encoding="utf-8")))
    assert {"_chat_adapter", "_llm_adapter"} <= cached, cached  # the scan still sees the two it was written for

    declared = set(ConversationalNPCMixin._UNSAVED_ATTRS) | set(MynxLLMMixin._UNSAVED_ATTRS)
    assert cached <= declared, f"adapter caches not declared in an _UNSAVED_ATTRS: {sorted(cached - declared)}"
