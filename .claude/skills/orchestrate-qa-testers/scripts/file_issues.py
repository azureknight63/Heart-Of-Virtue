"""File the issues declared in a spec module with gh, recording URLs next to it.

    python file_issues.py --spec <path>/issues_spec.py            # dry run: titles + labels
    python file_issues.py --spec <path>/issues_spec.py --go       # create them
    python file_issues.py --spec <path>/issues_spec.py --go --only key1,key2

The spec is a Python module exposing ISSUES = [{key, title, labels, body}, ...]
(see assets/issues_spec_template.py). Filing is idempotent per key: URLs are
written to issues_filed.json beside the spec and already-filed keys are skipped,
so a crash halfway never double-files. Titles are checked for non-ASCII because
gh on Windows has mangled em dashes in the past; labels are checked against the
repo so a typo fails before the first issue goes out.
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("HOV_QA_ROOT") or Path(__file__).resolve().parents[4])


def load_spec(path: Path):
    spec = importlib.util.spec_from_file_location("issues_spec", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.ISSUES


def repo_labels():
    r = subprocess.run(["gh", "label", "list", "--limit", "100", "--json", "name", "-q", ".[].name"],
                       cwd=str(ROOT), capture_output=True, text=True)
    return set(r.stdout.split()) if r.returncode == 0 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    spec_path = Path(args.spec).resolve()
    issues = load_spec(spec_path)
    out = spec_path.parent / "issues_filed.json"
    filed = json.loads(out.read_text()) if out.exists() else {}
    only = set(filter(None, args.only.split(",")))

    problems = []
    labels = repo_labels()
    for issue in issues:
        bad = [c for c in issue["title"] if ord(c) > 127]
        if bad:
            problems.append(f"{issue['key']}: non-ASCII in title {bad!r}")
        if labels is not None:
            missing = set(issue["labels"]) - labels
            if missing:
                problems.append(f"{issue['key']}: unknown labels {sorted(missing)}")
    if problems:
        print("\n".join(problems))
        sys.exit(2)

    for issue in issues:
        key = issue["key"]
        if only and key not in only:
            continue
        if key in filed:
            print(f"skip {key}: already filed {filed[key]}")
            continue
        print(f"{'FILE' if args.go else 'DRY '} [{', '.join(issue['labels'])}] {issue['title']}")
        if not args.go:
            continue
        body_path = spec_path.parent / f"issue_{key}.md"
        body_path.write_text(issue["body"], encoding="utf-8")
        cmd = ["gh", "issue", "create", "--title", issue["title"], "--body-file", str(body_path)]
        for label in issue["labels"]:
            cmd += ["--label", label]
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  FAILED: {r.stderr.strip()[:300]}")
            continue
        url = r.stdout.strip().splitlines()[-1]
        filed[key] = url
        out.write_text(json.dumps(filed, indent=1))
        print(f"  -> {url}")


if __name__ == "__main__":
    main()
