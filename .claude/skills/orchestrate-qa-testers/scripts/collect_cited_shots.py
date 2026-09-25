"""collect_cited_shots.py — copy only the screenshots a QA report actually cites.

    python collect_cited_shots.py <report.md> --from <dir>[,<dir>...] [--also <dir>[,<dir>...]] [--dest <dir>] [--dry-run]

Why this exists: triage-and-report.md says to copy the tester reports and only
the *cited* screenshots into docs/qa/<run>/ — "13 screenshots ~= 3.6 MB was
acceptable; 130 was not". A driver run under logs/qa/<tag>/shots/ can produce
far more shots than a report cites; this script does the citation-matching
and copying so the orchestrator doesn't do it by hand (and doesn't quietly
drag along a shot nobody referenced).

What counts as a citation: qa_driver.py's ``shot(label)`` names files
``{driver_name}_{shot_n:03d}_{safe_label}.png`` (`safe_label` is `label` with
anything but alnum/-/_ turned into `_`, truncated to 60 chars). Reports cite
these inside backtick code spans, in two observed styles (both appear in the
existing docs/qa/*.md reports):

  - full filename, with or without a leading path: `` `T3_011_postfight_reload_stuck.png` ``
    or `` `logs/qa/runs-0917/shots/T2_001_t2_wallniche_takeall_fail.png` `` — matched by
    exact filename (the basename, case-insensitively).
  - bare "name_NNN" stem, usually under a `shots/` path segment: `` `shots/V1_001` `` —
    the label is dropped, so this is matched by *prefix*: any source file whose
    stem is exactly the citation or starts with "<citation>_".

Only backtick-quoted spans are scanned (that's how every existing report cites
a screenshot); anything else in prose is not treated as a citation. This is a
deliberate scoping choice, not an oversight — see the module's own tests for
what does and doesn't count.

For each citation, all matching files across the ``--from`` source
directories (searched recursively) are copied into ``--dest`` (default:
``<report stem>/shots/`` next to the report). Prints three sections: what was
copied, what was cited but not found anywhere in the source directories
(WARN, and the process exits non-zero), and the total copied size (WARN above
~10 MB, per triage-and-report.md's "130 was not" guidance). ``--dry-run``
does the citation search and prints the same report without copying
anything. Copying is idempotent: re-running overwrites each destination file
with the same bytes rather than duplicating it.

``--also <dir>[,<dir>...]`` additionally scans every ``*.md`` file in the
given directories (non-recursive) for citations — use it for a run's
``tester-reports/`` folder so a screenshot only a tester's own report cites
(not the consolidated report) still gets pulled in.
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

_SHOT_STEM_RE = re.compile(r"^([A-Za-z][A-Za-z0-9]*)_(\d{3})(?:_([A-Za-z0-9_-]+))?$")
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif"}
_BACKTICK_RE = re.compile(r"`([^`]+)`")
_WARN_BYTES = 10 * 1024 * 1024  # ~10 MB, per triage-and-report.md


class Citation:
    """A single screenshot reference found in a report."""

    def __init__(self, raw, stem, has_ext):
        self.raw = raw  # the exact backtick span, for reporting
        self.stem = stem  # filename stem, e.g. "V1_001" or "T3_011_postfight_reload_stuck"
        self.has_ext = has_ext  # True: match full filename exactly; False: prefix match


def _basename(span):
    """Last path segment of a (possibly path-like) backtick span."""
    return span.replace("\\", "/").rsplit("/", 1)[-1]


def extract_citations(text):
    """Find screenshot citations inside backtick spans of `text`."""
    citations = []
    for span in _BACKTICK_RE.findall(text):
        span = span.strip()
        if not span:
            continue
        base = _basename(span)
        ext = ""
        stem = base
        dot = base.rfind(".")
        if dot > 0:
            candidate_ext = base[dot:].lower()
            if candidate_ext in _IMAGE_EXTS:
                ext = candidate_ext
                stem = base[:dot]
        if not _SHOT_STEM_RE.match(stem):
            continue
        if ext:
            citations.append(Citation(raw=span, stem=stem + ext, has_ext=True))
        else:
            # Bare "name_NNN" (or "name_NNN_label") style: only treat it as a
            # citation when it clearly points at a shots location, to avoid
            # matching an unrelated backticked identifier that happens to fit
            # the name_NNN shape.
            if "shots/" in span.replace("\\", "/").lower() or "/" not in span:
                citations.append(Citation(raw=span, stem=stem, has_ext=False))
    return citations


def collect_report_texts(report_path, also_dirs):
    """Yield (source_path, text) for the report plus any --also markdown files."""
    yield report_path, report_path.read_text(encoding="utf-8")
    for d in also_dirs:
        d = Path(d)
        if d.is_file():
            yield d, d.read_text(encoding="utf-8")
        elif d.is_dir():
            for md in sorted(d.glob("*.md")):
                yield md, md.read_text(encoding="utf-8")


def index_source_files(source_dirs):
    """Map lowercase filename -> Path, and lowercase stem -> [Path, ...], across all source dirs."""
    by_filename = {}
    by_stem = {}
    for d in source_dirs:
        d = Path(d)
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*")):
            if not f.is_file() or f.suffix.lower() not in _IMAGE_EXTS:
                continue
            by_filename.setdefault(f.name.lower(), []).append(f)
            by_stem.setdefault(f.stem.lower(), []).append(f)
    return by_filename, by_stem


def resolve_citation(citation, by_filename, by_stem):
    """Return the list of source Paths a citation resolves to (possibly empty)."""
    if citation.has_ext:
        return list(by_filename.get(citation.stem.lower(), []))
    key = citation.stem.lower()
    matches = list(by_stem.get(key, []))
    if matches:
        return matches
    prefix = key + "_"
    matches = []
    for stem_key, paths in by_stem.items():
        if stem_key.startswith(prefix):
            matches.extend(paths)
    return matches


def run(report_path, source_dirs, also_dirs, dest_dir, dry_run):
    report_path = Path(report_path)
    all_texts = list(collect_report_texts(report_path, also_dirs))

    citations = {}  # stem-key -> Citation (dedupe by raw citation identity)
    for _src, text in all_texts:
        for c in extract_citations(text):
            key = (c.stem.lower(), c.has_ext)
            citations.setdefault(key, c)

    by_filename, by_stem = index_source_files(source_dirs)

    copied = []  # (Citation, resolved Path)
    missing = []  # Citation
    for c in citations.values():
        resolved = resolve_citation(c, by_filename, by_stem)
        if not resolved:
            missing.append(c)
            continue
        for path in resolved:
            copied.append((c, path))

    # Dedupe by resolved path (a citation and its prefix cousin could both hit the same file).
    seen_paths = set()
    unique_copied = []
    for c, path in copied:
        if path in seen_paths:
            continue
        seen_paths.add(path)
        unique_copied.append((c, path))
    copied = unique_copied

    if not dry_run and copied:
        dest_dir.mkdir(parents=True, exist_ok=True)
        for _c, path in copied:
            shutil.copy2(path, dest_dir / path.name)

    total_bytes = sum(path.stat().st_size for _c, path in copied)

    print(f"Report: {report_path}")
    print(f"Sources: {', '.join(str(Path(d)) for d in source_dirs)}")
    print(f"Dest: {dest_dir}{' (dry-run, not written)' if dry_run else ''}")
    print()
    if copied:
        verb = "Would copy" if dry_run else "Copied"
        print(f"{verb} {len(copied)} file(s):")
        for _c, path in sorted(copied, key=lambda cp: cp[1].name):
            print(f"  {path.name}  <-  {path}")
    else:
        print("Nothing to copy.")
    print()
    if missing:
        print(f"WARN: {len(missing)} cited screenshot(s) not found in any source dir:")
        for c in sorted(missing, key=lambda c: c.stem):
            print(f"  WARN: {c.raw!r} (looked for stem {c.stem!r})")
        print()
    total_mb = total_bytes / (1024 * 1024)
    print(f"Total size: {total_bytes} bytes ({total_mb:.2f} MB)")
    if total_bytes > _WARN_BYTES:
        print(f"WARN: total size exceeds ~10 MB ({total_mb:.2f} MB) — trim the citation list.")

    return 1 if missing else 0


def build_arg_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("report", help="path to the report .md file")
    parser.add_argument(
        "--from",
        dest="from_dirs",
        required=True,
        help="comma-separated source directories to search for shot files (searched recursively)",
    )
    parser.add_argument(
        "--also",
        dest="also_dirs",
        default="",
        help="comma-separated directories of tester reports (*.md) to also scan for citations",
    )
    parser.add_argument(
        "--dest",
        default=None,
        help="destination directory (default: <report stem>/shots/ next to the report)",
    )
    parser.add_argument("--dry-run", action="store_true", help="report what would be copied without copying")
    return parser


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    report_path = Path(args.report)
    source_dirs = [s.strip() for s in args.from_dirs.split(",") if s.strip()]
    also_dirs = [s.strip() for s in args.also_dirs.split(",") if s.strip()]
    dest_dir = Path(args.dest) if args.dest else report_path.parent / report_path.stem / "shots"
    return run(report_path, source_dirs, also_dirs, dest_dir, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
