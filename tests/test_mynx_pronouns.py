# Ensure local src package modules are importable during pytest collection
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'src'))

import os
from src.npc import Mynx

class DummyRoom:
    def __init__(self):
        self.description = "A mossy grove with shadowed ferns and a shallow stream."
        self.items_here = []
        self.objects_here = []
        self.npcs_here = []


class DummyNPC:
    def __init__(self, name, description="An NPC."):
        self.name = name
        self.description = description


def make_mynx_in_room(name="Snookums"):
    m = Mynx(name=name)
    r = DummyRoom()
    m.current_room = r
    r.npcs_here.append(m)
    return m, r


def test_jean_possessive_not_attributed_to_mynx():
    """Ensure Jean's possessions (his boots) are not converted to the mynx's possessive."""
    m, r = make_mynx_in_room("Snookums")
    # Simulate a raw LLM string where Jean's boots are mentioned with gendered pronoun
    raw = "Snookums circles Jean curiously, its tail flicking as it sniffs at the air near his boots."
    # roster_set includes Jean and the mynx name
    roster = {"Jean", m.name}
    cleaned = m._sanitize_mynx_llm_text(raw, roster)
    enforced = m._enforce_pronouns_and_names(cleaned, roster)
    # Should preserve 'his boots' referring to Jean (not converted to 'its boots')
    assert "his boots" in enforced or "Jean's boots" in enforced
    assert "its boots" not in enforced


def test_mynx_possessive_kept_for_mynx_only():
    """If the sentence clearly refers to the mynx, the mynx possessive should be allowed."""
    m, r = make_mynx_in_room("Snookums")
    raw = "Snookums pads along, its whiskers brushing against the dew on its tail."  # redundant but valid
    roster = {"Jean", m.name}
    cleaned = m._sanitize_mynx_llm_text(raw, roster)
    enforced = m._enforce_pronouns_and_names(cleaned, roster)
    assert "its tail" in enforced


def test_other_npc_name_preserved_and_not_mapped_to_mynx():
    """An adjacent NPC's name should be preserved and not turned into mynx possessive."""
    m, r = make_mynx_in_room("Snookums")
    other = DummyNPC("Maru", "A stoic traveler in patched leathers.")
    r.npcs_here.append(other)
    raw = "Snookums darts toward Maru, sniffing at Maru's satchel near his knee."
    roster = {"Jean", m.name, other.name}
    cleaned = m._sanitize_mynx_llm_text(raw, roster)
    enforced = m._enforce_pronouns_and_names(cleaned, roster)
    # Maru's possessive should be preserved (Maru's satchel or their satchel) and not become 'its'
    assert "Maru's satchel" in enforced or "their satchel" in enforced
    assert "its satchel" not in enforced


def test_sentence_with_both_jean_and_mynx_prioritizes_jean_for_jean_pronouns():
    """When a sentence includes both Jean and the mynx, Jean's pronouns should be mapped to Jean where clear."""
    m, r = make_mynx_in_room("Snookums")
    raw = "Snookums curls up by Jean as he checks his bootlaces, then Snookums circles him."  # includes 'he' and 'his'
    roster = {"Jean", m.name}
    cleaned = m._sanitize_mynx_llm_text(raw, roster)
    enforced = m._enforce_pronouns_and_names(cleaned, roster)
    # 'his bootlaces' should refer to Jean
    assert "his bootlaces" in enforced or "Jean's bootlaces" in enforced
    assert "its bootlaces" not in enforced
