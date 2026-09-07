"""qa.py — client for qa_driver.py.

    python qa.py PORT ping|url|text|aria|where|state|pending|allerrors
    python qa.py PORT shot LABEL
    python qa.py PORT -c "page.get_by_role('button', name='Move North').click()"
    python qa.py PORT exec < snippet.py      (or a heredoc on stdin: multi-line Python)
    python qa.py PORT quit

Inside exec code you have: page, context, browser (Playwright), api (requests
session with the Bearer token), API (base url), get(path), post(path, payload),
text(), aria(), shot(label), wait(ms), where(), state(), pending(),
hit_test(locator), raw_click(locator), all_errors(), plus json, re, time.
A single expression returns its value; statements may print() or set `result`.
Every call also prints the console/network events recorded since the last one.
"""
import json
import sys

import requests

SUGAR = {
    "url": "page.url", "text": "text()", "aria": "aria()", "where": "where()",
    "state": "state()", "pending": "pending()", "allerrors": "all_errors()",
}


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    port, cmd = int(sys.argv[1]), sys.argv[2]
    base = f"http://127.0.0.1:{port}"
    if cmd == "ping":
        print(json.dumps(requests.get(base + "/ping", timeout=10).json(), indent=1))
        return
    if cmd == "quit":
        print(requests.post(base + "/quit", json={}, timeout=10).text)
        return
    if cmd == "shot":
        code = f"shot({json.dumps(sys.argv[3] if len(sys.argv) > 3 else 'shot')})"
    elif cmd == "-c":
        code = sys.argv[3]
    elif cmd == "exec":
        code = sys.stdin.read()
    elif cmd in SUGAR:
        code = SUGAR[cmd]
    else:
        print(__doc__)
        sys.exit(2)
    r = requests.post(base + "/exec", json={"code": code}, timeout=300).json()
    if r.get("stdout"):
        print(r["stdout"], end="" if r["stdout"].endswith("\n") else "\n")
    res = r.get("result")
    if res is not None:
        print(res if isinstance(res, str) else json.dumps(res, indent=1))
    if r.get("error"):
        print("## ERROR\n" + r["error"])
    if r.get("new_events"):
        print("## new browser events (console/network) since last call:")
        for e in r["new_events"]:
            print(" ", json.dumps(e))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
