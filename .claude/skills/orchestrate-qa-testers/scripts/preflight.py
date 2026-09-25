"""Preflight for a live-browser QA run: everything that bit us once, checked in one go.

    python preflight.py [--ports 5001,3001,5002,3000] [--testers 4] [--llm]

Prints a PASS/WARN/FAIL line per check and exits non-zero on any FAIL. Run it
before starting stacks; fix the FAILs, read the WARNs. --llm adds provider,
model-pin and OpenRouter-quota checks (see references/gotchas.md and the
project memory note "Live browser QA toolkit" -- an LLM-scoped run has died
twice from things this section now catches before dispatch: an exhausted
free tier and a pinned model slug the vendor withdrew).
"""
import argparse
import ctypes
import importlib
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

try:
    import requests
except ImportError:  # pragma: no cover - only the --llm quota probe needs it
    requests = None

ROOT = Path(os.environ.get("HOV_QA_ROOT") or Path(__file__).resolve().parents[4])
MB_PER_TESTER = 450  # headless-shell Chromium + its share of a tester agent, measured 2026-09-06
_ENABLED_TRUE_VALUES = ("1", "true", "True")  # mirrors ai.llm_client._ENABLED_TRUE_VALUES
_OPENROUTER_KEY_URL = "https://openrouter.ai/api/v1/key"  # memory note 2026-09-17 probe


def line(status, msg):
    print(f"{status:4} {msg}")
    return status == "FAIL"


def venv_python():
    for cand in (ROOT / ".venv" / "Scripts" / "python.exe", ROOT / ".venv" / "bin" / "python"):
        if cand.exists():
            return str(cand)
    return None


def available_mb():
    if os.name == "nt":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        st = MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
        return st.ullAvailPhys // (1024 * 1024)
    try:
        for row in open("/proc/meminfo"):
            if row.startswith("MemAvailable:"):
                return int(row.split()[1]) // 1024
    except Exception:
        pass
    return None


def port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


# ---------------------------------------------------------------------------
# --llm section
#
# Derives the provider list from ai.llm_client instead of hardcoding names,
# and re-implements (rather than instantiates) NpcChatLLMAdapter's chain
# selection: building the real adapter runs model discovery/validation over
# the network at __init__, which is exactly the metered spend this preflight
# check must not cause. See ai/llm_client.py's _provider_chain docstring for
# the rules this mirrors; re-check that docstring if this drifts.
# ---------------------------------------------------------------------------

def _truthy(value):
    return (value or "").strip() in _ENABLED_TRUE_VALUES


def provider_registry():
    """{provider name: credential env var or None} derived from ai.llm_client.

    ``ollama`` is added by hand: it is not in
    ``_OPENAI_COMPATIBLE_PROVIDERS`` (it needs no credential, only an
    optional address override), but it is a real fallback-chain member.
    Raises on import failure; callers decide the fallback.
    """
    sys.path.insert(0, str(ROOT))
    mod = importlib.import_module("ai.llm_client")
    registry = {name: cfg.get("key_env") for name, cfg in mod._OPENAI_COMPATIBLE_PROVIDERS.items()}
    registry["ollama"] = None
    return registry


def provider_configured(name, key_env, env):
    """Whether ``name`` has a usable credential in ``env`` (a plain dict).

    Mirrors ``ai.llm_client._ollama_base_url``/``_provider_credential``:
    Ollama needs no secret, so an *unset* OLLAMA_BASE_URL means "the default
    localhost port" (configured), while an explicitly *blank* value is how an
    operator says "no local host here" (not configured). Every other
    provider is configured only when its key env var is non-blank.
    """
    if name == "ollama":
        raw = env.get("OLLAMA_BASE_URL")
        return True if raw is None else raw.strip() != ""
    return bool((env.get(key_env) or "").strip())


def npc_chat_provider_chain(env, configured):
    """The provider order NPC chat would try, per ``ai.llm_client``'s rules.

    ``configured`` is a ``name -> bool`` mapping (see ``provider_configured``)
    so this stays pure and network-free. Deliberately omits the real
    adapter's saturation filtering (``GenericLLMClient._provider_available``)
    -- that is transient, in-process state a static preflight check cannot
    see, and a stale reading there must never make a chain look emptier than
    it is.
    """
    named = (env.get("NPC_CHAT_LLM_PROVIDER") or "").strip().lower()
    inherited = (env.get("MYNX_LLM_PROVIDER") or "").strip().lower()
    provider = named or inherited or "ollama"
    if provider == "none":
        return []
    if not named:
        # A credential merely sitting in the environment is not consent to
        # dial a provider nobody named for chat -- only naming one arms the
        # fallback chain at all.
        return [provider]
    raw_fallback = (env.get("NPC_CHAT_LLM_FALLBACK") or "").strip()
    fallback = None if not raw_fallback else raw_fallback in _ENABLED_TRUE_VALUES
    if fallback is False:
        return [provider]
    if provider == "ollama" and not fallback:
        return ["ollama"]
    chain = [provider]
    for name in ("openrouter", "groq", "cerebras"):
        if name not in chain and configured.get(name):
            chain.append(name)
    if "ollama" not in chain and configured.get("ollama"):
        chain.append("ollama")
    return chain


def probe_openrouter_quota(key, requester=None):
    """GET OpenRouter's own key-info endpoint; the key goes only to OpenRouter.

    Returns a dict of the fields the 2026-09-17 QA run found useful
    (usage/limit/is_free_tier plus ``free_model_daily_requests`` when the
    account exposes it) or raises. Callers must never print ``key`` itself --
    only this summary. ``requester`` defaults to a real short-timeout GET;
    tests inject a fake so nothing here ever touches the network.
    """
    if requester is None:
        if requests is None:
            raise RuntimeError("requests is not installed")

        def requester(k):
            r = requests.get(_OPENROUTER_KEY_URL, headers={"Authorization": "Bearer " + k}, timeout=5)
            r.raise_for_status()
            return r.json()
    payload = requester(key)
    data = payload.get("data", payload) if isinstance(payload, dict) else {}
    return {
        "usage": data.get("usage"),
        "limit": data.get("limit"),
        "is_free_tier": data.get("is_free_tier"),
        "free_model_daily_requests": data.get("free_model_daily_requests"),
    }


OLLAMA_DEFAULT_URL = "http://localhost:11434"


def ollama_reachable(base_url, timeout=1.5):
    """True when an Ollama server answers at ``base_url`` (GET /api/tags).

    A configured base URL says nothing about a running server: on 2026-09-24
    none was running, so "ollama configured" would have been false comfort.
    """
    import urllib.request
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/api/tags", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def llm_checks(env, probe=None, registry=None, ollama_probe=None):
    """PASS/WARN/FAIL lines for the --llm section, given a plain env dict.

    ``probe`` (``key -> dict``, see ``probe_openrouter_quota``) and
    ``registry`` (see ``provider_registry``) are injectable so this runs with
    no network and no repo import in tests. Real callers omit both.
    ``ollama_probe`` (``base_url -> bool``) is only called when supplied;
    ``main`` passes ``ollama_reachable``. Without it, a configured Ollama is
    reported as unverified rather than assumed to be running.
    """
    results = []

    npc_on = _truthy(env.get("NPC_CHAT_LLM_ENABLED"))
    mynx_on = _truthy(env.get("MYNX_LLM_ENABLED"))
    combat_raw = (env.get("COMBAT_LLM_ENABLED") or "").strip()
    combat_on = _truthy(combat_raw) if combat_raw else mynx_on  # falls back to MYNX_LLM_ENABLED
    gates_msg = ("LLM gates: NPC_CHAT_LLM_ENABLED=%s MYNX_LLM_ENABLED=%s COMBAT_LLM_ENABLED=%s "
                 "(start_stack.py --no-llm forces all three off)" % (npc_on, mynx_on, combat_on))
    results.append(("PASS", gates_msg))

    if registry is None:
        try:
            registry = provider_registry()
        except Exception as exc:
            results.append(("WARN", "could not derive the provider list from ai.llm_client: %s" % exc))
            registry = {}

    configured = {name: provider_configured(name, key_env, env) for name, key_env in registry.items()}
    unreachable = set()
    for name in sorted(registry):
        key_env = registry[name]
        label = key_env if key_env else "OLLAMA_BASE_URL (no secret; default localhost unless blanked)"
        if name == "ollama" and configured[name]:
            base_url = (env.get("OLLAMA_BASE_URL") or "").strip() or OLLAMA_DEFAULT_URL
            if ollama_probe is None:
                results.append(("WARN", "provider ollama: configured, reachability not checked (%s)" % base_url))
                continue
            if not ollama_probe(base_url):
                # Not a usable fallback: it no longer counts as usable, and the
                # chain line marks it (the engine still tries it; it just fails).
                unreachable.add(name)
                results.append(("WARN", "provider ollama: configured but nothing answers at %s" % base_url))
                continue
            results.append(("PASS", "provider ollama: reachable at %s" % base_url))
            continue
        results.append(("PASS" if configured[name] else "WARN",
                        "provider %s: %s (%s)" % (name, "configured" if configured[name] else "not configured", label)))

    usable_count = sum(1 for name, v in configured.items() if v and name not in unreachable)
    if (npc_on or mynx_on or combat_on) and usable_count <= 1:
        one_provider_msg = ("only %d LLM provider usable -- exhaustion means canned lines; "
                            "cap LLM to one tester" % usable_count)
        results.append(("WARN", one_provider_msg))

    if registry:
        chain = npc_chat_provider_chain(env, configured)
        live = [name for name in chain if name not in unreachable]
        shown = [name + (" (unreachable)" if name in unreachable else "") for name in chain]
        results.append(("PASS" if len(live) > 1 else "WARN",
                        "NPC chat provider chain (this feature's real fallback; Mynx/combat dial one "
                        "provider only): %s" % (shown or "[] -- chat disabled or provider unset to none")))

    for pin_var in ("MYNX_LLM_MODEL", "NPC_CHAT_LLM_MODEL", "COMBAT_LLM_MODEL"):
        val = (env.get(pin_var) or "").strip()
        if not val or val.lower() == "auto":
            results.append(("PASS", "%s=%r (auto/unset ranks and re-checks nightly)" % (pin_var, val or "auto")))
        elif val.endswith(":free"):
            pin_msg = ("%s=%r pinned to a specific :free model -- it saturates independently of "
                       "quota and a withdrawn slug 404s silently (issue #533); prefer auto" % (pin_var, val))
            results.append(("WARN", pin_msg))
        else:
            results.append(("PASS", "%s=%r (pinned, not a free-tier slug)" % (pin_var, val)))

    key = (env.get("OPENROUTER_API_KEY") or "").strip()
    if not key:
        results.append(("WARN", "OPENROUTER_API_KEY unset; cannot probe OpenRouter quota"))
    else:
        try:
            info = probe_openrouter_quota(key, requester=probe)
            results.append(("PASS", "OpenRouter key info: %s" % info))
        except Exception as exc:
            probe_msg = ("OpenRouter quota probe failed (%s); check by hand before "
                         "promising an LLM-scoped run" % exc)
            results.append(("WARN", probe_msg))

    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ports", default="5001,3001,5002,3000")
    ap.add_argument("--testers", type=int, default=4)
    ap.add_argument("--llm", action="store_true",
                    help="also check LLM providers, model pins and OpenRouter quota (off by default)")
    args = ap.parse_args()
    failed = False

    py = venv_python()
    failed |= line("PASS" if py else "FAIL", f"repo venv python: {py or 'not found under .venv'}")

    # Playwright + a Chromium that actually launches (the pip package wants its own build)
    if py:
        r = subprocess.run([py, "-c", "from playwright.sync_api import sync_playwright\n"
                            "with sync_playwright() as p:\n b=p.chromium.launch(headless=True); print(b.version); b.close()"],
                           capture_output=True, text=True, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        ok = r.returncode == 0
        failed |= line("PASS" if ok else "FAIL",
                       f"playwright + chromium: {r.stdout.strip() if ok else 'pip install playwright && python -m playwright install chromium'}")

    # Accepted Socket.IO origins — the port guard start_stack.py enforces
    sys.path.insert(0, str(ROOT))
    try:
        cfg = importlib.import_module("src.api.config")
        origins = list(cfg.Config.CORS_ORIGINS)
        line("PASS", f"accepted Vite origins (Socket.IO): {origins}")
    except Exception as exc:
        origins = []
        failed |= line("FAIL", f"could not import src.api.config: {exc}")

    for p in [int(x) for x in args.ports.split(",") if x]:
        free = port_free(p)
        note = ""
        if p < 4000 and origins and f"http://localhost:{p}" not in origins:
            note = "  <- NOT an accepted origin; combat streaming would die on this Vite port"
        failed |= line("PASS" if free else "FAIL", f"port {p} free{note}")

    # .env facts the run depends on
    env_path = ROOT / ".env"
    keys = {}
    if env_path.exists():
        for row in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in row and not row.lstrip().startswith("#"):
                k, v = row.split("=", 1)
                keys[k.strip()] = v.strip()
        line("PASS" if keys.get("FLASK_ENV") == "testing" else "WARN",
             f".env FLASK_ENV={keys.get('FLASK_ENV')!r} (qa_api.py forces testing anyway)")
        line("WARN" if keys.get("GITHUB_TOKEN") else "PASS",
             ".env has GITHUB_TOKEN" + (" — qa_api.py blanks it; never start tools/run_api.py for QA" if keys.get("GITHUB_TOKEN") else " unset"))
        line("PASS", f".env NPC_CHAT_LLM_ENABLED={keys.get('NPC_CHAT_LLM_ENABLED')!r} MYNX_LLM_ENABLED={keys.get('MYNX_LLM_ENABLED')!r} "
                     f"(LLM talk costs real tokens when enabled)")
    else:
        line("WARN", ".env missing — LLM chat and Turso will be off")

    mb = available_mb()
    need = args.testers * MB_PER_TESTER + 1200
    if mb is not None:
        failed |= line("PASS" if mb >= need else ("WARN" if mb >= need * 0.7 else "FAIL"),
                       f"available memory {mb} MB; ~{need} MB wanted for {args.testers} testers + 2 stacks")

    if os.name == "nt":
        r = subprocess.run(["tasklist"], capture_output=True, text=True)
        stray = r.stdout.lower().count("chrome-headless-shell")
        line("WARN" if stray else "PASS", f"stray chrome-headless-shell processes: {stray}" + (" — kill them first" if stray else ""))

    line("PASS" if shutil.which("gh") else "WARN", "gh CLI " + ("present" if shutil.which("gh") else "missing — issues must be filed by hand"))
    if shutil.which("gh"):
        r = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
        line("PASS" if r.returncode == 0 else "WARN", "gh auth " + ("ok" if r.returncode == 0 else "not logged in"))

    if args.llm:
        # Process env wins over .env, matching dotenv's override=False: a
        # per-gate override set in the parent shell (references/gotchas.md,
        # "Per-gate LLM control") is what would actually take effect.
        llm_env = {**keys, **os.environ}
        for status, msg in llm_checks(llm_env, ollama_probe=ollama_reachable):
            line(status, msg)

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
