"""Preflight for a live-browser QA run: everything that bit us once, checked in one go.

    python preflight.py [--ports 5001,3001,5002,3000] [--testers 4]

Prints a PASS/WARN/FAIL line per check and exits non-zero on any FAIL. Run it
before starting stacks; fix the FAILs, read the WARNs.
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

ROOT = Path(os.environ.get("HOV_QA_ROOT") or Path(__file__).resolve().parents[4])
MB_PER_TESTER = 450  # headless-shell Chromium + its share of a tester agent, measured 2026-09-06


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ports", default="5001,3001,5002,3000")
    ap.add_argument("--testers", type=int, default=4)
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
    if env_path.exists():
        keys = {}
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

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
