"""Unit tests for teardown.py's planning/execution logic: no real process I/O.

Every test builds a fake list of "listening processes" and checks the plan
and the (fake-executed) outcome. Real killing, real port scans and real
/quit POSTs are never exercised here -- see teardown.py's own docstrings for
the real-process functions this deliberately does not import for testing.

Run with:
    .venv/Scripts/python.exe -m pytest .claude/skills/orchestrate-qa-testers/scripts/tests/test_teardown.py -q -n0
"""
import importlib.util
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location("teardown", SCRIPTS_DIR / "teardown.py")
teardown = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(teardown)


# --- parse_ports -------------------------------------------------------

def test_parse_ports_comma_list():
    assert teardown.parse_ports("5001,3000,3001") == [3000, 3001, 5001]


def test_parse_ports_range():
    assert teardown.parse_ports("7001-7003") == [7001, 7002, 7003]


def test_parse_ports_mixed_and_dedup():
    assert teardown.parse_ports("5001,5001,7001-7002") == [5001, 7001, 7002]


# --- is_qa_owned ---------------------------------------------------------

def test_qa_api_process_is_owned():
    cmd = r"C:\repo\.venv\Scripts\python.exe C:\repo\.claude\skills\orchestrate-qa-testers\scripts\qa_api.py"
    assert teardown.is_qa_owned(cmd, 5001) == "api"


def test_qa_driver_process_is_owned():
    cmd = "python .claude/skills/orchestrate-qa-testers/scripts/qa_driver.py --name T1 --ctrl 7001"
    assert teardown.is_qa_owned(cmd, 7001) == "driver"


def test_vite_on_matching_qa_port_is_owned():
    cmd = r'"C:\Program Files\nodejs\node.exe" .../vite/bin/vite.js --port 3001 --strictPort'
    assert teardown.is_qa_owned(cmd, 3001) == "vite"


def test_vite_on_a_different_port_is_not_owned_for_this_port():
    # The command line names a different port than the one being torn down --
    # must not be claimed as QA's just because it says "vite" somewhere.
    cmd = "node .../vite/bin/vite.js --port 3002 --strictPort"
    assert teardown.is_qa_owned(cmd, 3000) is None


def test_unrelated_process_on_a_qa_port_is_never_claimed():
    # The exact scenario the skill's author called out: the user's own dev
    # server sitting on :3000. Must be spared, not swept up as "probably ours".
    cmd = r'"C:\Program Files\nodejs\node.exe" C:\Users\dev\my-other-app\server.js --port 3000'
    assert teardown.is_qa_owned(cmd, 3000) is None


def test_blank_cmdline_is_never_claimed():
    assert teardown.is_qa_owned("", 5001) is None
    assert teardown.is_qa_owned(None, 5001) is None


# --- plan_teardown ---------------------------------------------------------

def _proc(pid, port, cmdline):
    return {"pid": pid, "port": port, "cmdline": cmdline}


def test_plan_marks_qa_api_for_kill():
    processes = [_proc(101, 5001, "python qa_api.py")]
    plan = teardown.plan_teardown(processes, driver_ports=[])
    assert plan[0]["tag"] == "api"
    assert plan[0]["action"] == "kill"


def test_plan_marks_driver_control_port_for_graceful_quit():
    processes = [_proc(202, 7001, "python qa_driver.py --ctrl 7001")]
    plan = teardown.plan_teardown(processes, driver_ports=[7001, 7002])
    assert plan[0]["tag"] == "driver"
    assert plan[0]["action"] == "graceful_quit"


def test_plan_marks_vite_on_qa_port_for_kill():
    processes = [_proc(303, 3001, "node vite --port 3001 --strictPort")]
    plan = teardown.plan_teardown(processes, driver_ports=[])
    assert plan[0]["tag"] == "vite"
    assert plan[0]["action"] == "kill"


def test_plan_spares_the_non_qa_process_on_port_3000():
    processes = [
        _proc(404, 3000, r"node C:\Users\dev\my-other-app\server.js --port 3000"),
        _proc(303, 3001, "node vite --port 3001 --strictPort"),
    ]
    plan = teardown.plan_teardown(processes, driver_ports=[])
    by_port = {p["port"]: p for p in plan}
    assert by_port[3000]["action"] == "skip"
    assert by_port[3000]["tag"] is None
    assert by_port[3001]["action"] == "kill"


def test_plan_does_not_mutate_input_dicts():
    original = _proc(101, 5001, "python qa_api.py")
    processes = [original]
    teardown.plan_teardown(processes, driver_ports=[])
    assert original == {"pid": 101, "port": 5001, "cmdline": "python qa_api.py"}


def test_plan_empty_processes_gives_empty_plan():
    assert teardown.plan_teardown([], driver_ports=[7001]) == []


# --- execute_teardown --------------------------------------------------

def test_dry_run_reports_plan_and_calls_no_killer():
    processes = [_proc(101, 5001, "python qa_api.py"), _proc(202, 7001, "python qa_driver.py")]
    plan = teardown.plan_teardown(processes, driver_ports=[7001])
    killed = []
    quit_calls = []
    results = teardown.execute_teardown(
        plan,
        quit_driver=lambda pid, port: quit_calls.append((pid, port)) or True,
        kill_pid=lambda pid: killed.append(pid),
        dry_run=True,
    )
    assert killed == []
    assert quit_calls == []
    assert all(status == "PASS" for status, _ in results)
    assert any("would kill" in msg for _, msg in results)
    assert any("would graceful_quit" in msg for _, msg in results)


def test_dry_run_never_calls_killer_even_for_skipped_process():
    processes = [_proc(404, 3000, "node my-other-app/server.js --port 3000")]
    plan = teardown.plan_teardown(processes, driver_ports=[])
    killed = []
    results = teardown.execute_teardown(plan, kill_pid=lambda pid: killed.append(pid), dry_run=True)
    assert killed == []
    assert results == [("WARN", results[0][1])]
    assert "left running" in results[0][1]


def test_execute_skip_never_calls_killer_in_a_real_run_either():
    processes = [_proc(404, 3000, "node my-other-app/server.js --port 3000")]
    plan = teardown.plan_teardown(processes, driver_ports=[])
    killed = []
    results = teardown.execute_teardown(plan, kill_pid=lambda pid: killed.append(pid), dry_run=False)
    assert killed == []
    assert results[0][0] == "WARN"


def test_execute_kill_calls_killer_with_the_right_pid():
    processes = [_proc(101, 5001, "python qa_api.py")]
    plan = teardown.plan_teardown(processes, driver_ports=[])
    killed = []
    results = teardown.execute_teardown(plan, kill_pid=lambda pid: killed.append(pid), dry_run=False)
    assert killed == [101]
    assert results[0][0] == "PASS"


def test_execute_graceful_quit_success_never_calls_killer():
    processes = [_proc(202, 7001, "python qa_driver.py")]
    plan = teardown.plan_teardown(processes, driver_ports=[7001])
    killed = []
    results = teardown.execute_teardown(
        plan, quit_driver=lambda pid, port: True, kill_pid=lambda pid: killed.append(pid), dry_run=False,
    )
    assert killed == []
    assert results[0][0] == "PASS"
    assert "quit gracefully" in results[0][1]


def test_execute_graceful_quit_failure_falls_back_to_killer():
    processes = [_proc(202, 7001, "python qa_driver.py")]
    plan = teardown.plan_teardown(processes, driver_ports=[7001])
    killed = []
    results = teardown.execute_teardown(
        plan, quit_driver=lambda pid, port: False, kill_pid=lambda pid: killed.append(pid), dry_run=False,
    )
    assert killed == [202]
    assert results[0][0] == "PASS"
    assert "force-killed" in results[0][1]


def test_vite_needs_start_stacks_exact_signature():
    qa = "node frontend/node_modules/vite/bin/vite.js --port 3001 --strictPort"
    assert teardown.is_qa_owned(qa, 3001) == "vite"
    # A developer's own vite on the same port, without --strictPort: spared.
    assert teardown.is_qa_owned("node node_modules/vite/bin/vite.js --port 3001", 3001) is None
    # Port digits as a prefix of a longer number are not this port.
    assert teardown.is_qa_owned("node vite.js --port 30001 --strictPort", 3000) is None
    # Plain `npm run dev` (no port) on :3000 is spared.
    assert teardown.is_qa_owned("node node_modules/vite/bin/vite.js", 3000) is None
