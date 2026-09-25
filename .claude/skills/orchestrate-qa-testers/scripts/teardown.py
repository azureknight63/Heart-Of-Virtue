"""Tear down a live-browser QA run: replaces the manual Phase 4 teardown step.

    python teardown.py [--ports 5001,5002,5003,5004,3000,3001]
                        [--driver-ports 7001-7012] [--dry-run]

For each recorded QA port, finds the process listening on it, confirms by
command line that it actually belongs to this skill (qa_api.py / vite on
that exact port / qa_driver.py), and stops it -- a graceful POST /quit for a
driver control port (see qa_driver.py's do_POST), a kill for an API or Vite
process. A process on a QA port whose command line does not match anything
QA-owned is left alone and reported as a WARN: killing the wrong thing on a
shared port (a developer's own dev server on :3000, say) is worse than a
port this run leaves open. Afterwards it verifies no listener remains on any
recorded port and no chrome-headless-shell process is still running, and
exits non-zero if either is true. --dry-run prints the plan and kills
nothing.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:  # pragma: no cover - only the graceful /quit needs it
    requests = None

ROOT = Path(os.environ.get("HOV_QA_ROOT") or Path(__file__).resolve().parents[4])
DEFAULT_PORTS = "5001,5002,5003,5004,3000,3001"
DEFAULT_DRIVER_PORTS = "7001-7012"


def line(status, msg):
    print(f"{status:4} {msg}")
    return status == "FAIL"


def parse_ports(spec):
    """"5001,3000" or "7001-7012" (or a mix, comma-separated) -> a sorted int list."""
    ports = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            ports.update(range(int(lo), int(hi) + 1))
        else:
            ports.add(int(part))
    return sorted(ports)


# ---------------------------------------------------------------------------
# Pure planning functions -- no process I/O, so these are what the tests
# exercise directly with fake process lists.
# ---------------------------------------------------------------------------

def is_qa_owned(cmdline, port):
    """Tag a listening process as QA-owned from its command line, or None.

    Deliberately conservative: a process on a QA port that does not mention
    one of this skill's own scripts (qa_api.py, qa_driver.py) or vite bound
    to THIS exact port is never assumed to be ours -- it is reported and
    left alone. A developer's own dev server sitting on :3000 must survive a
    teardown call exactly like this one.
    """
    low = (cmdline or "").lower()
    if "qa_api.py" in low:
        return "api"
    if "qa_driver.py" in low:
        return "driver"
    # start_stack.py's exact signature (`--port N --strictPort`), not "vite
    # and the digits somewhere": a developer's own `vite --port 3001` must
    # survive, and "3000" must not match "30001".
    if "vite" in low and "--strictport" in low and re.search(r"--port[ =]%d(?!\d)" % port, low):
        return "vite"
    return None


def plan_teardown(processes, driver_ports):
    """The action for each listening process: 'graceful_quit', 'kill' or 'skip'.

    ``processes`` is a list of ``{"pid", "port", "cmdline"}``. ``driver_ports``
    is the set of ports that are qa_driver.py control ports (graceful /quit
    preferred over a kill, per qa_driver.py's own shutdown handler). Returns
    a new list of dicts with ``tag``, ``action`` and ``reason`` added; input
    dicts are not mutated.
    """
    driver_ports = set(driver_ports)
    plan = []
    for proc in processes:
        port, cmdline = proc["port"], proc.get("cmdline", "")
        tag = is_qa_owned(cmdline, port)
        entry = dict(proc, tag=tag)
        if tag is None:
            entry["action"] = "skip"
            skip_reason = ("command line does not name a QA script (qa_api.py / qa_driver.py) or "
                           "vite bound to port %d -- cannot confirm this is QA's; left running" % port)
            entry["reason"] = skip_reason
        elif tag == "driver" and port in driver_ports:
            entry["action"] = "graceful_quit"
            entry["reason"] = "QA driver control port (POST /quit before a kill)"
        else:
            entry["action"] = "kill"
            entry["reason"] = "QA %s process" % tag
        plan.append(entry)
    return plan


def execute_teardown(plan, quit_driver=None, kill_pid=None, dry_run=False):
    """Carry out (or, dry-run, describe) the plan from ``plan_teardown``.

    ``quit_driver(pid, port) -> bool`` and ``kill_pid(pid) -> None`` are
    injectable so tests never touch a real process. A driver that does not
    answer /quit falls back to ``kill_pid``, matching the SKILL.md guidance
    to prefer graceful shutdown but not depend on it.
    """
    results = []
    for item in plan:
        pid, port, tag, action = item["pid"], item["port"], item["tag"], item["action"]
        if action == "skip":
            results.append(("WARN", "left running: pid=%s port=%s (%s)" % (pid, port, item["reason"])))
            continue
        if dry_run:
            results.append(("PASS", "would %s: pid=%s port=%s tag=%s" % (action, pid, port, tag)))
            continue
        if action == "graceful_quit":
            ok = bool(quit_driver and quit_driver(pid, port))
            if ok:
                results.append(("PASS", "driver quit gracefully: pid=%s port=%s" % (pid, port)))
            elif kill_pid:
                kill_pid(pid)
                results.append(("PASS", "driver did not answer /quit; force-killed pid=%s port=%s" % (pid, port)))
            else:
                results.append(("WARN", "driver did not answer /quit and no killer was given: pid=%s" % pid))
        elif action == "kill":
            if kill_pid:
                kill_pid(pid)
            results.append(("PASS", "killed %s: pid=%s port=%s" % (tag, pid, port)))
    return results


# ---------------------------------------------------------------------------
# Real process I/O -- Windows primary (this box), POSIX fallback like
# preflight.py's available_mb/stray-chrome checks.
# ---------------------------------------------------------------------------

def _windows_listening_pids(port):
    r = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
    pids = set()
    for row in r.stdout.splitlines():
        parts = row.split()
        if len(parts) == 5 and parts[0].upper() == "TCP" and parts[3].upper() == "LISTENING":
            if parts[1].endswith(":%d" % port) and parts[4].isdigit():
                pids.add(int(parts[4]))
    return pids


def _posix_listening_pids(port):
    try:
        r = subprocess.run(["lsof", "-i", ":%d" % port, "-sTCP:LISTEN", "-t"],
                           capture_output=True, text=True)
        return {int(p) for p in r.stdout.split() if p.strip().isdigit()}
    except FileNotFoundError:
        return set()


def _windows_cmdlines(pids):
    """{pid: command line} for every pid in ``pids`` that still exists."""
    if not pids:
        return {}
    filt = " or ".join("ProcessId=%d" % p for p in pids)
    ps_cmd = ("Get-CimInstance Win32_Process -Filter \"%s\" | "
              "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress" % filt)
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
    out = {}
    try:
        data = json.loads(r.stdout or "[]")
        rows = data if isinstance(data, list) else [data]
        for row in rows:
            if row and row.get("ProcessId") is not None:
                out[int(row["ProcessId"])] = row.get("CommandLine") or ""
    except Exception:
        pass
    return out


def _posix_cmdlines(pids):
    out = {}
    for pid in pids:
        try:
            with open("/proc/%d/cmdline" % pid, "rb") as f:
                out[pid] = f.read().replace(b"\0", b" ").decode("utf-8", "replace")
        except Exception:
            out[pid] = ""
    return out


def listening_processes(ports):
    """Real ``{"pid", "port", "cmdline"}`` rows for every listener on ``ports``."""
    by_pid_port = []
    for port in ports:
        pids = _windows_listening_pids(port) if os.name == "nt" else _posix_listening_pids(port)
        for pid in pids:
            by_pid_port.append((pid, port))
    all_pids = {pid for pid, _ in by_pid_port}
    cmdlines = _windows_cmdlines(all_pids) if os.name == "nt" else _posix_cmdlines(all_pids)
    return [{"pid": pid, "port": port, "cmdline": cmdlines.get(pid, "")} for pid, port in by_pid_port]


def real_quit_driver(pid, port, timeout=5):
    if requests is None:
        return False
    try:
        requests.post("http://127.0.0.1:%d/quit" % port, json={}, timeout=timeout)
        return True
    except Exception:
        return False


def real_kill_pid(pid):
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True)
    else:
        subprocess.run(["kill", "-9", str(pid)], capture_output=True)


def stray_chrome_headless_count():
    if os.name == "nt":
        r = subprocess.run(["tasklist"], capture_output=True, text=True)
        return r.stdout.lower().count("chrome-headless-shell")
    try:
        r = subprocess.run(["pgrep", "-fc", "chrome-headless-shell"], capture_output=True, text=True)
        return int(r.stdout.strip() or 0)
    except FileNotFoundError:
        return 0


def kill_stray_chrome_headless():
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/IM", "chrome-headless-shell.exe"], capture_output=True)
    else:
        subprocess.run(["pkill", "-9", "-f", "chrome-headless-shell"], capture_output=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ports", default=DEFAULT_PORTS,
                    help="QA API/Vite ports to check (comma list and/or N-M ranges)")
    ap.add_argument("--driver-ports", default=DEFAULT_DRIVER_PORTS,
                    help="qa_driver.py control ports (graceful /quit before a kill)")
    ap.add_argument("--dry-run", action="store_true", help="print the plan; kill nothing")
    args = ap.parse_args()

    ports = parse_ports(args.ports)
    driver_ports = parse_ports(args.driver_ports)
    all_ports = sorted(set(ports) | set(driver_ports))

    processes = listening_processes(all_ports)
    plan = plan_teardown(processes, driver_ports)
    if not plan:
        line("PASS", "nothing listening on any recorded QA port (%s)" % all_ports)

    for status, msg in execute_teardown(plan, quit_driver=real_quit_driver,
                                        kill_pid=real_kill_pid, dry_run=args.dry_run):
        line(status, msg)

    if args.dry_run:
        sys.exit(0)

    # A killed process can take a moment to release its socket.
    time.sleep(1.5 if plan else 0)

    failed = False
    for port in all_ports:
        pids = _windows_listening_pids(port) if os.name == "nt" else _posix_listening_pids(port)
        failed |= line("PASS" if not pids else "FAIL", "port %d: %s" % (port, "free" if not pids else "still listening (pid %s)" % sorted(pids)))

    stray = stray_chrome_headless_count()
    if stray and plan:
        # Only clean these up when this run actually tore something down --
        # a stray from a session this teardown call never touched is still
        # worth reporting, not silently swept.
        kill_stray_chrome_headless()
        time.sleep(1.0)
        stray = stray_chrome_headless_count()
    failed |= line("PASS" if not stray else "FAIL", "chrome-headless-shell processes: %d" % stray)

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
