"""Unit tests for preflight.py's --llm section: provider/chain/pin/quota checks.

No network and no repo import: every test injects its own ``env`` dict, a
fake ``registry`` and a fake ``probe`` (see ``llm_checks``'s docstring in
preflight.py). Run with:

    .venv/Scripts/python.exe -m pytest .claude/skills/orchestrate-qa-testers/scripts/tests/test_preflight_llm.py -q -n0
"""
import importlib.util
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location("preflight", SCRIPTS_DIR / "preflight.py")
preflight = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(preflight)

REGISTRY = {
    "openrouter": "OPENROUTER_API_KEY",
    "groq": "GROQ_API_KEY",
    "cerebras": "CEREBRAS_API_KEY",
    "ollama": None,
}


def statuses(results):
    return {msg: status for status, msg in results}


def find(results, needle):
    return [(s, m) for s, m in results if needle in m]


# --- provider_configured ---------------------------------------------------

def test_provider_configured_key_env_present():
    assert preflight.provider_configured("openrouter", "OPENROUTER_API_KEY", {"OPENROUTER_API_KEY": "sk-1"})


def test_provider_configured_key_env_absent():
    assert not preflight.provider_configured("openrouter", "OPENROUTER_API_KEY", {})


def test_provider_configured_key_env_blank():
    assert not preflight.provider_configured("groq", "GROQ_API_KEY", {"GROQ_API_KEY": "   "})


def test_provider_configured_ollama_unset_is_default_localhost():
    # Unset OLLAMA_BASE_URL means "the default port", per ai.llm_client._ollama_base_url.
    assert preflight.provider_configured("ollama", None, {})


def test_provider_configured_ollama_explicit_blank_means_no_local_host():
    assert not preflight.provider_configured("ollama", None, {"OLLAMA_BASE_URL": ""})


def test_provider_configured_ollama_explicit_url():
    assert preflight.provider_configured("ollama", None, {"OLLAMA_BASE_URL": "http://localhost:11434"})


# --- npc_chat_provider_chain -----------------------------------------------

def test_chain_provider_none_disables_chat():
    env = {"NPC_CHAT_LLM_PROVIDER": "none"}
    assert preflight.npc_chat_provider_chain(env, {}) == []


def test_chain_no_named_provider_is_just_the_inherited_default():
    # Nothing named for chat specifically: a credential merely present in the
    # environment is not consent to arm the fallback chain.
    env = {}
    configured = {"openrouter": True, "groq": True, "cerebras": True, "ollama": True}
    assert preflight.npc_chat_provider_chain(env, configured) == ["ollama"]


def test_chain_inherited_mynx_provider_also_stays_unfanned():
    env = {"MYNX_LLM_PROVIDER": "openrouter"}
    configured = {"openrouter": True, "groq": True, "cerebras": True, "ollama": True}
    assert preflight.npc_chat_provider_chain(env, configured) == ["openrouter"]


def test_chain_named_provider_fans_out_to_configured_providers_only():
    env = {"NPC_CHAT_LLM_PROVIDER": "openrouter"}
    configured = {"openrouter": True, "groq": False, "cerebras": True, "ollama": True}
    assert preflight.npc_chat_provider_chain(env, configured) == ["openrouter", "cerebras", "ollama"]


def test_chain_fallback_0_pins_to_named_provider_whatever_it_is():
    env = {"NPC_CHAT_LLM_PROVIDER": "groq", "NPC_CHAT_LLM_FALLBACK": "0"}
    configured = {"openrouter": True, "groq": True, "cerebras": True, "ollama": True}
    assert preflight.npc_chat_provider_chain(env, configured) == ["groq"]


def test_chain_named_ollama_stays_local_without_explicit_fallback():
    env = {"NPC_CHAT_LLM_PROVIDER": "ollama"}
    configured = {"openrouter": True, "groq": True, "cerebras": True, "ollama": True}
    assert preflight.npc_chat_provider_chain(env, configured) == ["ollama"]


def test_chain_named_ollama_with_fallback_1_fans_out():
    env = {"NPC_CHAT_LLM_PROVIDER": "ollama", "NPC_CHAT_LLM_FALLBACK": "1"}
    configured = {"openrouter": True, "groq": False, "cerebras": False, "ollama": True}
    assert preflight.npc_chat_provider_chain(env, configured) == ["ollama", "openrouter"]


# --- probe_openrouter_quota (fake requester injected; no network) ---------

def test_probe_returns_expected_fields():
    def fake(key):
        assert key == "sk-secret"
        return {"data": {"usage": 3, "limit": 10, "is_free_tier": True,
                "free_model_daily_requests": {"used": 5, "limit": 50, "remaining": 45}}}
    info = preflight.probe_openrouter_quota("sk-secret", requester=fake)
    assert info == {"usage": 3, "limit": 10, "is_free_tier": True,
                    "free_model_daily_requests": {"used": 5, "limit": 50, "remaining": 45}}


def test_probe_propagates_requester_failure():
    def fake(key):
        raise RuntimeError("boom")
    try:
        preflight.probe_openrouter_quota("sk-secret", requester=fake)
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass


# --- llm_checks: the composed PASS/WARN report -----------------------------

def test_llm_checks_never_prints_the_openrouter_key():
    env = {"OPENROUTER_API_KEY": "sk-should-not-leak", "NPC_CHAT_LLM_ENABLED": "1"}
    results = preflight.llm_checks(env, probe=lambda k: {"data": {}}, registry=REGISTRY)
    for _, msg in results:
        assert "sk-should-not-leak" not in msg


def test_llm_checks_warns_on_single_usable_provider():
    # No local Ollama on this box (2026-09-24 run) is exactly why this WARN
    # matters -- an unblanked OLLAMA_BASE_URL always reads as usable.
    env = {"NPC_CHAT_LLM_ENABLED": "1", "OPENROUTER_API_KEY": "sk-1", "OLLAMA_BASE_URL": ""}
    results = preflight.llm_checks(env, probe=lambda k: {"data": {}}, registry=REGISTRY)
    warnings = find(results, "only 1 LLM provider usable")
    assert warnings and warnings[0][0] == "WARN"


def test_llm_checks_no_single_provider_warning_when_two_are_usable():
    env = {"NPC_CHAT_LLM_ENABLED": "1", "OPENROUTER_API_KEY": "sk-1", "GROQ_API_KEY": "sk-2"}
    results = preflight.llm_checks(env, probe=lambda k: {"data": {}}, registry=REGISTRY)
    assert not find(results, "only 1 LLM provider usable")


def test_llm_checks_no_provider_warning_when_llm_entirely_disabled():
    # Every gate off: an unconfigured remote key is not a reason to WARN.
    env = {}
    results = preflight.llm_checks(env, probe=lambda k: {"data": {}}, registry=REGISTRY)
    assert not find(results, "only 0 LLM provider usable")


def test_llm_checks_warns_on_pinned_free_model():
    env = {"MYNX_LLM_MODEL": "stepfun/step-3.5-flash:free"}
    results = preflight.llm_checks(env, probe=None, registry=REGISTRY)
    hits = find(results, "MYNX_LLM_MODEL='stepfun/step-3.5-flash:free' pinned")
    assert hits and hits[0][0] == "WARN"


def test_llm_checks_passes_on_auto_model():
    env = {"NPC_CHAT_LLM_MODEL": "auto"}
    results = preflight.llm_checks(env, probe=None, registry=REGISTRY)
    hits = find(results, "NPC_CHAT_LLM_MODEL='auto'")
    assert hits and hits[0][0] == "PASS"


def test_llm_checks_passes_on_pinned_non_free_model():
    env = {"COMBAT_LLM_MODEL": "openai/gpt-4o-mini"}
    results = preflight.llm_checks(env, probe=None, registry=REGISTRY)
    hits = find(results, "COMBAT_LLM_MODEL='openai/gpt-4o-mini'")
    assert hits and hits[0][0] == "PASS"


def test_llm_checks_reports_all_three_gates():
    env = {"NPC_CHAT_LLM_ENABLED": "1", "MYNX_LLM_ENABLED": "0", "COMBAT_LLM_ENABLED": "1"}
    results = preflight.llm_checks(env, probe=None, registry=REGISTRY)
    gate_lines = find(results, "LLM gates:")
    assert len(gate_lines) == 1
    assert "NPC_CHAT_LLM_ENABLED=True" in gate_lines[0][1]
    assert "MYNX_LLM_ENABLED=False" in gate_lines[0][1]
    assert "COMBAT_LLM_ENABLED=True" in gate_lines[0][1]


def test_llm_checks_combat_gate_falls_back_to_mynx_when_unset():
    env = {"MYNX_LLM_ENABLED": "1"}
    results = preflight.llm_checks(env, probe=None, registry=REGISTRY)
    gate_lines = find(results, "LLM gates:")
    assert "COMBAT_LLM_ENABLED=True" in gate_lines[0][1]


def test_llm_checks_warns_when_openrouter_key_unset():
    env = {}
    results = preflight.llm_checks(env, probe=None, registry=REGISTRY)
    hits = find(results, "OPENROUTER_API_KEY unset")
    assert hits and hits[0][0] == "WARN"


def test_llm_checks_warns_on_probe_failure_without_crashing():
    def failing_probe(key):
        raise TimeoutError("no route to host")
    env = {"OPENROUTER_API_KEY": "sk-1"}
    results = preflight.llm_checks(env, probe=failing_probe, registry=REGISTRY)
    hits = find(results, "OpenRouter quota probe failed")
    assert hits and hits[0][0] == "WARN"


def test_llm_checks_falls_back_to_empty_registry_on_import_failure(monkeypatch):
    def boom():
        raise ImportError("ai.llm_client unavailable in this venv")
    monkeypatch.setattr(preflight, "provider_registry", boom)
    env = {"NPC_CHAT_LLM_ENABLED": "1"}
    results = preflight.llm_checks(env, probe=None, registry=None)
    hits = find(results, "could not derive the provider list")
    assert hits and hits[0][0] == "WARN"
    # No crash, and no provider/chain lines fabricated from a missing registry.
    assert not find(results, "NPC chat provider chain")


def test_an_unreachable_ollama_is_not_counted_as_a_fallback():
    """2026-09-24: the default URL was "configured" and nothing was running."""
    env = {"NPC_CHAT_LLM_ENABLED": "1", "OPENROUTER_API_KEY": ""}
    results = preflight.llm_checks(env, probe=None, registry=REGISTRY, ollama_probe=lambda url: False)
    hit = find(results, "provider ollama")
    assert hit and hit[0][0] == "WARN" and "nothing answers" in hit[0][1]
    assert find(results, "only 0 LLM provider usable")
    chain = find(results, "NPC chat provider chain")
    # The engine still tries it, so it stays in the chain -- marked, and WARN.
    assert chain and chain[0][0] == "WARN" and "ollama (unreachable)" in chain[0][1]


def test_a_reachable_ollama_passes_and_stays_in_the_chain():
    env = {"NPC_CHAT_LLM_ENABLED": "1"}
    seen = []
    results = preflight.llm_checks(env, probe=None, registry=REGISTRY,
                                   ollama_probe=lambda url: seen.append(url) or True)
    assert seen == [preflight.OLLAMA_DEFAULT_URL]
    hit = find(results, "provider ollama")
    assert hit and hit[0][0] == "PASS"


def test_ollama_is_unverified_without_a_probe():
    results = preflight.llm_checks({}, probe=None, registry=REGISTRY)
    hit = find(results, "provider ollama")
    assert hit and hit[0][0] == "WARN" and "not checked" in hit[0][1]
