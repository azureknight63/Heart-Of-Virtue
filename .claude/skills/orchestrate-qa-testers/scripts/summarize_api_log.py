"""summarize_api_log.py -- triage evidence for REST QA testers.

    python summarize_api_log.py FILE_OR_DIR [FILE_OR_DIR ...] [--repeat-n N] [--json]

Why this exists: on 2026-09-24 five REST testers (`scripts/qa_api_client.py`)
filed five Criticals and none survived triage (`references/tester-roles.md`,
"REST API testers"). Two patterns did the damage and both are visible only by
reading the request log, not any single response: tester A4 resent
`move "Turn"` about 1,200 times because it never noticed the response's
`input_type` wanted something else, and issue #683 was a `GET` that silently
consumed a victory scene (`references/triage-and-report.md`, point 5). This
script mines `qa_api_client.py`'s `<NAME>_api.jsonl` request logs (records
with keys `t`, `m`, `path`, `req`, `status`, `body`) for both patterns plus
the ordinary triage staples, so an orchestrator gets them from one command
instead of re-deriving them by hand every run.

Per file, it prints:

- request count and a status histogram (2xx/4xx/5xx/None -- `None` is a
  transport failure, `qa_api_client.py` records `status: null` for those);
- `success: false` responses (the game's refusal convention -- 200 + body --
  see `references/tester-roles.md`), grouped by `body["message"]`;
- repeat runs: the same method+path+request body sent N or more times in a
  row (default 20). For each, the response's `input_type` is pulled out
  (checked at the top level and inside a nested "combat" payload, since the
  primer says it can be nested under the combat payload) so the reader sees
  what the game was actually asking for instead of the resend;
- state changes after a GET: consecutive GET requests of the same path whose
  bodies differ outside a small, documented ignore list of fields that
  legitimately tick between polls. This is deliberately simple (top-level key
  diff only) per the skill's "keep this heuristic simple and documented";
- 404s grouped by path (phantom endpoints from a bad primer -- see
  `scripts/list_routes.py`, the source of truth for real endpoints).

`--json` prints one JSON object per file instead of the text report.

Assumption (documented per the skill's format-guess rule): "differ in a way
that matters" is implemented as "the set of top-level keys/values in the
response body differs, once IGNORE_FIELDS is removed". IGNORE_FIELDS below is
the documented, small ignore list the skill asks for -- extend it if a new
run finds another legitimately-ticking field.
"""
import argparse
import json
import sys
from pathlib import Path

DEFAULT_REPEAT_N = 20

# Fields that legitimately change between two otherwise-identical polls and so
# must not trip the "state changed after a GET" heuristic. Extend this list
# (with a comment saying which run found the new one) rather than loosening
# the comparison generally.
IGNORE_FIELDS = {
    "timestamp", "server_time", "time", "ts",
    "beat", "beats", "beat_count", "elapsed", "elapsed_ms", "tick", "tick_count",
}


def load_records(path):
    records = []
    for raw in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            records.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return records


def _status_bucket(status):
    if status is None:
        return "None"
    if 200 <= status < 300:
        return "2xx"
    if 400 <= status < 500:
        return "4xx"
    if 500 <= status < 600:
        return "5xx"
    return str(status)


def _find_key(obj, key, _depth=0):
    """Depth-first search for `key` anywhere in a JSON-shaped structure."""
    if _depth > 6 or obj is None:
        return None
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            found = _find_key(v, key, _depth + 1)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_key(v, key, _depth + 1)
            if found is not None:
                return found
    return None


def _req_key(rec):
    req_json = json.dumps(rec.get("req"), sort_keys=True, ensure_ascii=False)
    return (rec.get("m"), rec.get("path"), req_json)


def find_repeats(records, n):
    """Consecutive runs of the identical method+path+request body, length >= n."""
    repeats = []
    i = 0
    total = len(records)
    while i < total:
        j = i + 1
        while j < total and _req_key(records[j]) == _req_key(records[i]):
            j += 1
        run_len = j - i
        if run_len >= n:
            last = records[j - 1]
            body = last.get("body")
            repeats.append({
                "method": last.get("m"), "path": last.get("path"), "count": run_len,
                "req": last.get("req"), "input_type": _find_key(body, "input_type"),
                "first_t": records[i].get("t"), "last_t": last.get("t"),
            })
        i = j
    return repeats


def _body_diff_matters(a, b):
    """True if two response bodies differ outside IGNORE_FIELDS (top-level only)."""
    if not isinstance(a, dict) or not isinstance(b, dict):
        return a != b
    keys = (set(a) | set(b)) - IGNORE_FIELDS - {"_status"}
    return any(a.get(k) != b.get(k) for k in keys)


def _describe_diff(a, b):
    if not isinstance(a, dict) or not isinstance(b, dict):
        return "body changed"
    keys = (set(a) | set(b)) - IGNORE_FIELDS - {"_status"}
    changed = [k for k in sorted(keys) if a.get(k) != b.get(k)]
    parts = []
    for k in changed:
        av, bv = a.get(k), b.get(k)
        if isinstance(av, list) and isinstance(bv, list) and len(bv) < len(av):
            parts.append(f"{k}: {len(av)} -> {len(bv)} items (shrank)")
        elif av and not bv:
            parts.append(f"{k}: {av!r} -> {bv!r} (disappeared)")
        else:
            parts.append(f"{k} changed")
    return "; ".join(parts) if parts else "body changed"


def find_state_changes_after_get(records):
    """Consecutive GET/GET pairs on the same path whose bodies differ meaningfully."""
    changes = []
    for i in range(len(records) - 1):
        a, b = records[i], records[i + 1]
        if a.get("m") != "GET" or b.get("m") != "GET":
            continue
        if a.get("path") != b.get("path"):
            continue
        if not _body_diff_matters(a.get("body"), b.get("body")):
            continue
        changes.append({
            "path": a.get("path"), "t1": a.get("t"), "t2": b.get("t"),
            "diff": _describe_diff(a.get("body"), b.get("body")),
        })
    return changes


def summarize_file(path, repeat_n=DEFAULT_REPEAT_N):
    records = load_records(path)
    hist = {}
    for r in records:
        bucket = _status_bucket(r.get("status"))
        hist[bucket] = hist.get(bucket, 0) + 1

    success_false = {}
    for r in records:
        body = r.get("body")
        if isinstance(body, dict) and body.get("success") is False:
            msg = body.get("message", "(no message)")
            success_false[msg] = success_false.get(msg, 0) + 1

    not_found = {}
    for r in records:
        if r.get("status") == 404:
            not_found[r.get("path")] = not_found.get(r.get("path"), 0) + 1

    return {
        "file": str(path),
        "count": len(records),
        "status_histogram": hist,
        "success_false": success_false,
        "repeat_n": repeat_n,
        "repeats": find_repeats(records, repeat_n),
        "state_changes_after_get": find_state_changes_after_get(records),
        "not_found_404": not_found,
    }


def format_text(summary):
    out = [f"=== {summary['file']} ===",
           f"requests: {summary['count']}  status: {summary['status_histogram']}"]

    if summary["success_false"]:
        out.append("success: false, grouped by message:")
        for msg, count in sorted(summary["success_false"].items(), key=lambda kv: -kv[1]):
            out.append(f"  x{count}  {msg}")
    else:
        out.append("success: false -- none")

    if summary["repeats"]:
        out.append(f"repeat runs (>= {summary['repeat_n']} sent consecutively):")
        for r in summary["repeats"]:
            head = f"  x{r['count']}  {r['method']} {r['path']}  req={r['req']}"
            tail = f"input_type={r['input_type']!r}  ({r['first_t']}..{r['last_t']})"
            out.append(f"{head}  {tail}")
    else:
        out.append("repeat runs -- none")

    if summary["state_changes_after_get"]:
        out.append("state changed after a GET (no POST in between):")
        for c in summary["state_changes_after_get"]:
            out.append(f"  {c['path']}  {c['t1']} -> {c['t2']}: {c['diff']}")
    else:
        out.append("state changes after a GET -- none")

    if summary["not_found_404"]:
        out.append("404s by path:")
        for p, count in sorted(summary["not_found_404"].items(), key=lambda kv: -kv[1]):
            out.append(f"  x{count}  {p}")
    else:
        out.append("404s -- none")

    return "\n".join(out)


def _resolve_inputs(paths):
    files = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            files.extend(sorted(p.glob("*.jsonl")))
        else:
            files.append(p)
    return files


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="request-log JSONL file(s) or a directory of them")
    ap.add_argument(
        "--repeat-n", type=int, default=DEFAULT_REPEAT_N,
        help=f"minimum consecutive identical requests to report (default {DEFAULT_REPEAT_N})")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    files = _resolve_inputs(args.paths)
    if not files:
        print("no .jsonl files found", file=sys.stderr)
        sys.exit(2)

    summaries = [summarize_file(f, args.repeat_n) for f in files]
    if args.json:
        print(json.dumps(summaries, indent=1, ensure_ascii=False))
    else:
        for s in summaries:
            print(format_text(s))
            print()


if __name__ == "__main__":
    main()
