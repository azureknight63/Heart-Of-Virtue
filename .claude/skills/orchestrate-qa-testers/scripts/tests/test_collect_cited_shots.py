"""Tests for collect_cited_shots.py.

Run with the repo venv:
    .venv/Scripts/python.exe -m pytest .claude/skills/orchestrate-qa-testers/scripts/tests/test_collect_cited_shots.py -q -n0

tmp_path fixtures build a small report + source shots directory covering:
a cited-and-present file (copied), an uncited file (left alone), a
cited-and-missing file (reported as WARN, non-zero exit), both citation
styles (full filename, and bare "name_NNN" under a shots/ path), and
--dry-run (reports the same plan but copies nothing).
"""
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import collect_cited_shots as ccs  # noqa: E402


def _make_source_dir(tmp_path, filenames):
    src = tmp_path / "shots"
    src.mkdir()
    for name in filenames:
        (src / name).write_bytes(b"fake-png-bytes")
    return src


def test_extract_citations_full_filename_with_path():
    text = "Evidence: `logs/qa/runs-0917/shots/T2_001_t2_wallniche_takeall_fail.png` shows it."
    citations = ccs.extract_citations(text)
    assert len(citations) == 1
    assert citations[0].has_ext is True
    assert citations[0].stem == "T2_001_t2_wallniche_takeall_fail.png"


def test_extract_citations_bare_stem_under_shots_prefix():
    text = "verified in a headless browser (`shots/V1_001`, `V1_003`)."
    citations = ccs.extract_citations(text)
    stems = sorted(c.stem for c in citations)
    assert stems == ["V1_001", "V1_003"]
    assert all(c.has_ext is False for c in citations)


def test_extract_citations_ignores_non_shot_backticks():
    text = "See `CombatManager.jsx:105` and `end_state.status`."
    assert ccs.extract_citations(text) == []


def test_extract_citations_ignores_prose_outside_backticks():
    text = "The file T3_011_postfight_reload_stuck.png is not backticked here."
    assert ccs.extract_citations(text) == []


def test_cited_and_present_file_is_copied(tmp_path):
    src = _make_source_dir(tmp_path, ["T3_011_postfight_reload_stuck.png"])
    report = tmp_path / "report.md"
    report.write_text("Evidence: `T3_011_postfight_reload_stuck.png`\n", encoding="utf-8")
    dest = tmp_path / "out" / "shots"

    rc = ccs.run(report, [str(src)], [], dest, dry_run=False)

    assert rc == 0
    assert (dest / "T3_011_postfight_reload_stuck.png").is_file()


def test_uncited_file_is_not_copied(tmp_path):
    src = _make_source_dir(
        tmp_path, ["T3_011_postfight_reload_stuck.png", "T3_012_unrelated_shot.png"]
    )
    report = tmp_path / "report.md"
    report.write_text("Evidence: `T3_011_postfight_reload_stuck.png`\n", encoding="utf-8")
    dest = tmp_path / "out" / "shots"

    ccs.run(report, [str(src)], [], dest, dry_run=False)

    assert (dest / "T3_011_postfight_reload_stuck.png").is_file()
    assert not (dest / "T3_012_unrelated_shot.png").exists()


def test_cited_and_missing_file_is_warned_and_nonzero_exit(tmp_path, capsys):
    src = _make_source_dir(tmp_path, ["T3_011_postfight_reload_stuck.png"])
    report = tmp_path / "report.md"
    report.write_text("Evidence: `T9_999_never_taken.png`\n", encoding="utf-8")
    dest = tmp_path / "out" / "shots"

    rc = ccs.run(report, [str(src)], [], dest, dry_run=False)
    out = capsys.readouterr().out

    assert rc == 1
    assert "WARN" in out
    assert "T9_999_never_taken.png" in out
    assert not dest.exists()


def test_both_citation_styles_resolve_same_run(tmp_path):
    src = _make_source_dir(
        tmp_path,
        ["V1_001_defeat_first_load.png", "T3_011_postfight_reload_stuck.png"],
    )
    report = tmp_path / "report.md"
    report.write_text(
        "Full name: `T3_011_postfight_reload_stuck.png`. "
        "Bare stem: `shots/V1_001`.\n",
        encoding="utf-8",
    )
    dest = tmp_path / "out" / "shots"

    rc = ccs.run(report, [str(src)], [], dest, dry_run=False)

    assert rc == 0
    assert (dest / "T3_011_postfight_reload_stuck.png").is_file()
    assert (dest / "V1_001_defeat_first_load.png").is_file()


def test_dry_run_copies_nothing_but_reports_plan(tmp_path, capsys):
    src = _make_source_dir(tmp_path, ["T3_011_postfight_reload_stuck.png"])
    report = tmp_path / "report.md"
    report.write_text("Evidence: `T3_011_postfight_reload_stuck.png`\n", encoding="utf-8")
    dest = tmp_path / "out" / "shots"

    rc = ccs.run(report, [str(src)], [], dest, dry_run=True)
    out = capsys.readouterr().out

    assert rc == 0
    assert not dest.exists()
    assert "Would copy" in out
    assert "T3_011_postfight_reload_stuck.png" in out


def test_also_dirs_scan_tester_reports_for_citations(tmp_path):
    src = _make_source_dir(tmp_path, ["T5_007_scene4_gorran_gate.png"])
    report = tmp_path / "report.md"
    report.write_text("Consolidated report cites nothing about T5.\n", encoding="utf-8")
    tester_dir = tmp_path / "tester-reports"
    tester_dir.mkdir()
    (tester_dir / "T5.md").write_text(
        "Screenshot `T5_007_scene4_gorran_gate.png`\n", encoding="utf-8"
    )
    dest = tmp_path / "out" / "shots"

    rc = ccs.run(report, [str(src)], [str(tester_dir)], dest, dry_run=False)

    assert rc == 0
    assert (dest / "T5_007_scene4_gorran_gate.png").is_file()


def test_copy_is_idempotent(tmp_path):
    src = _make_source_dir(tmp_path, ["T3_011_postfight_reload_stuck.png"])
    report = tmp_path / "report.md"
    report.write_text("Evidence: `T3_011_postfight_reload_stuck.png`\n", encoding="utf-8")
    dest = tmp_path / "out" / "shots"

    ccs.run(report, [str(src)], [], dest, dry_run=False)
    first_bytes = (dest / "T3_011_postfight_reload_stuck.png").read_bytes()
    rc = ccs.run(report, [str(src)], [], dest, dry_run=False)
    second_bytes = (dest / "T3_011_postfight_reload_stuck.png").read_bytes()

    assert rc == 0
    assert first_bytes == second_bytes
    assert len(list(dest.iterdir())) == 1


def test_total_size_warns_above_threshold(tmp_path, capsys):
    src = tmp_path / "shots"
    src.mkdir()
    big = src / "T1_001_big_shot.png"
    big.write_bytes(b"0" * (11 * 1024 * 1024))
    report = tmp_path / "report.md"
    report.write_text("Evidence: `T1_001_big_shot.png`\n", encoding="utf-8")
    dest = tmp_path / "out" / "shots"

    rc = ccs.run(report, [str(src)], [], dest, dry_run=False)
    out = capsys.readouterr().out

    assert rc == 0
    assert "WARN" in out
    assert "10 MB" in out
