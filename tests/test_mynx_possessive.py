import sys
from pathlib import Path

# Ensure src on path
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from src.npc import Mynx  # noqa

def test_mynx_possessive_preserved():
    m = Mynx(name="Snookums")
    raw = "Snookums leans into Jean's gentle petting, its fur bristling slightly with contentment."
    roster = ["Snookums"]
    sanitized = m._sanitize_mynx_llm_text(raw, roster)
    corrected = m._check_and_correct_mynx_text(sanitized, prompt="pet", roster=roster)
    assert corrected is not None
    # Ensure Jean's possessive is preserved
    assert "Jean's gentle petting" in corrected
    # Ensure we did NOT wrongly strip the possessive noun
    assert "it gentle petting" not in corrected
    # Basic sanity: first occurrence of Snookums may remain; pronoun use acceptable thereafter
    assert corrected.startswith("Snookums")

