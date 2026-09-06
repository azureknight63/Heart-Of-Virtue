"""Contract test: the instruction surfaces must not name repo paths that do not exist.

Modelled on ``tests/test_wire_field_contract.py`` and
``tests/test_move_categories_ui_contract.py`` -- same spirit: derive what one side
actually is, assert the other side actually matches, no mocking around the seam.

=== The bug class ===

Documentation rot has been this branch's dominant recurring defect. Every round of
review found the same shape: an instruction file confidently names a file that was
deleted or renamed, an agent reads it, believes it, and acts on it. Instances that
survived three separate correction rounds before this guard existed:

1. ``.github/copilot-instructions.md`` told you to run the game with
   ``python src/game.py``. That entry point went out with the terminal teardown;
   the game has been web-only for months.
2. The same file, and ``docs/API_DOCUMENTATION.md``, routed test work to
   ``tests/api/test_validators.py`` and ``tests/api/test_routes_integration.py``.
   Both were deleted when ``tests/api`` was rescued and pruned.
3. ``.github/copilot-instructions.md`` documented an "Update OpenAPI schema"
   workflow against ``src/api/schemas/openapi.py``. No such module exists, and
   grepping ``src/`` for "openapi" returns nothing at all.

A wrong instruction is worse than a missing one: a missing instruction makes the
reader look, a wrong one makes the reader confident. Fixing each instance by hand
is what the previous rounds did, and the class kept coming back. This test is the
generalisation -- it fails on the *next* one, not on these.

=== What is checked ===

Surfaces: root ``CLAUDE.md``, ``.claude/rules/*.md``, ``.claude/skills/*/SKILL.md``,
``.github/copilot-instructions.md``, and ``docs/**/*.md``.

From each surface, path-shaped tokens are pulled out of inline code spans, markdown
link targets, and fenced code blocks. A token counts as a repo-path claim only when
it contains a ``/`` *and* ends in a known source extension. Two deliberate
narrowings, both trading a little coverage for no false positives:

* **Bare filenames are not checked.** ``moves.py`` in prose references a concept,
  not a location, and resolving it would mean guessing at a directory.
* **Directory references are not checked.** Docs write ``src/api/routes/`` and
  ``moves/`` as shorthand relative to a prefix established a sentence earlier, and
  there is no reliable way to tell a wrong directory from a shorthand one.

A claim resolves if any file in the repo path index *ends with* it. Suffix matching
is deliberate: a doc that has just said "under ``frontend/src/``" and then writes
``hooks/useApi.js`` is being clear, not wrong. It does not blunt the guard against
the defect class -- nothing in the tree ends with ``src/game.py`` or
``tests/api/test_validators.py``, so all three regressions above still fail here.

=== Excused paths ===

Three escape hatches, in descending order of how comfortable you should be adding to
them. Each is a hard-coded, reviewable constant: a path is excused because someone
wrote down why, never because the scan quietly stopped looking.

``GENERATED_PREFIXES``   build and report output that is correctly not checked in.
``ILLUSTRATIVE_PATHS``   template paths (``yourmap.json``, ``ch0N.py``).
``DELIBERATELY_ABSENT``  (surface, path) pairs where a doc names something removed
                         or not yet built, on purpose.

``DELIBERATELY_ABSENT`` is the dangerous one, so ``test_no_unused_excuses`` asserts
every entry still describes a real unresolved reference. Fix the doc and the excuse
fails until you delete it; the list cannot quietly become a list of unfixed bugs.

``docs/archive/`` is skipped wholesale. Those are frozen milestone reports kept for
provenance -- they describe a tree that no longer exists, and "correcting" them
would falsify the record rather than fix anything.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Extensions that make a slash-bearing token a file-path claim rather than prose.
SOURCE_EXTENSIONS = frozenset(
    "py js jsx ts tsx md json ini yml yaml ps1 html sh txt cfg toml css sav".split()
)

# Directories whose contents are never checked in: build output, coverage reports,
# harness output, the virtualenv. Docs reference these legitimately ("open
# htmlcov/index.html"), and whether they exist depends on what you last ran --
# checking them would make this test's result depend on the developer's machine.
GENERATED_PREFIXES = (
    "htmlcov/",
    "dist/",
    "frontend/coverage/",
    "frontend/dist/",
    "coverage/",
    ".venv/",
    ".vscode/",
    "tools/browser_findings.json",
    "tools/devops-audit-",
    "bugs.json",
)

# Template paths: the doc is showing a shape to fill in, not naming a file.
ILLUSTRATIVE_PATHS = frozenset(
    {
        "src/story/ch0N.py",
        "story/ch0N.py",
        "docs/development/FILENAME.html",
        "tests/test_file.py",
        "src/resources/maps/yourmap.json",
        "src/components/MyComponent.jsx",
        "src/pages/MyPage.jsx",
        "src/api/models/user.py",
    }
)

# (surface, referenced path) -> why this doc names something that is not there.
# Keep the list short and every reason specific. An entry that stops being true
# fails test_no_unused_excuses, which is the point of having reasons at all.
DELIBERATELY_ABSENT = {
    # --- documents whose subject is the past ---
    (
        ".claude/rules/testing.md",
        "src/import_sync.py",
    ): "The sentence exists to say this module was retired. Naming it is the content.",
    (
        "docs/development/engine-history.md",
        "src/moves.py",
    ): "History of the moves package: records the split of src/moves.py into src/moves/.",
    (
        "docs/development/engine-history.md",
        "src/combat.py",
    ): "History of the terminal teardown: records the deletion of src/combat.py.",
    (
        "docs/qa-reports/qa-happy-path-2026-03-20.md",
        "src/moves.py",
    ): "Dated QA report. Accurate when written; editing it would falsify the record.",
    # --- design docs for content that is not built yet ---
    (
        "docs/lore/enemies/rock_rumbler.md",
        "src/tilesets/verdette_caverns.py",
    ): "Planned tileset. src/tilesets/ holds dark_grotto.py and grondelith_mineral_pools.py.",
    (
        "docs/lore/environments/eastern-approach/eastern-approach-profile.md",
        "src/resources/maps/eastern-approach.json",
    ): "Planned map, not yet authored.",
    (
        "docs/lore/environments/eastern-approach/eastern-approach-profile.md",
        "src/resources/maps/river-crossing.json",
    ): "Planned map, not yet authored.",
    (
        "docs/lore/environments/verdette-caverns/verdette-caverns-west-profile.md",
        "src/resources/maps/verdette-caverns-west.json",
    ): "Planned map, not yet authored.",
    (
        "docs/lore/environments/wailing-badlands/wailing-badlands-profile.md",
        "src/resources/maps/wailing-badlands.json",
    ): "Planned map, not yet authored.",
    (
        "docs/lore/environments/grondelith-mineral-pools/grondelith-mineral-pools-profile.md",
        "docs/lore/environments/mineral-pool-design-notes.md",
    ): "Planned design note, not yet written.",
    (
        "docs/lore/environments/grondia-city/grondia-city-profile.md",
        "docs/lore/environments/mineral-pool-design-notes.md",
    ): "Planned design note, not yet written.",
}

# Frozen milestone reports: accurate history of a tree that no longer exists.
SKIPPED_DOC_DIRS = ("archive",)

_CODE_SPAN = re.compile(r"`([^`\n]+)`")
_LINK_TARGET = re.compile(r"\]\(([^)\s]+)\)")
_FENCE = re.compile(r"^\s*```")
_TOKEN = re.compile(r"[A-Za-z0-9_.*/-]+")


def instruction_surfaces():
    """Every file an agent is expected to read as instruction, in scan order."""
    surfaces = [
        REPO_ROOT / "CLAUDE.md",
        REPO_ROOT / ".github" / "copilot-instructions.md",
    ]
    surfaces += sorted((REPO_ROOT / ".claude" / "rules").glob("*.md"))
    surfaces += sorted((REPO_ROOT / ".claude" / "skills").glob("*/SKILL.md"))
    surfaces += [
        path
        for path in sorted((REPO_ROOT / "docs").rglob("*.md"))
        if not any(part in SKIPPED_DOC_DIRS for part in path.parts)
    ]
    return [path for path in surfaces if path.is_file()]


def _repo_path_index():
    """Every file path in the tree, plus every suffix of every path.

    Suffix entries are what let a doc write ``hooks/useApi.js`` for
    ``frontend/src/hooks/useApi.js`` without tripping the guard.
    """
    ignored = {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        "htmlcov",
        "coverage",
        "dist",
        "build",
        ".pytest_cache",
        ".ruff_cache",
    }
    suffixes = set()
    for path in REPO_ROOT.rglob("*"):
        if any(part in ignored for part in path.parts):
            continue
        if not path.is_file():
            continue
        parts = path.relative_to(REPO_ROOT).as_posix().split("/")
        for start in range(len(parts)):
            suffixes.add("/".join(parts[start:]))
    return frozenset(suffixes)


PATH_INDEX = _repo_path_index()


def normalize_reference(raw):
    """Trim a raw token down to the path it claims, or to something is_path_claim rejects."""
    text = raw.split("::")[0].split("#")[0].strip()
    if "=" in text:  # --cov=src/api, CONFIG_FILE=config_dev.ini
        text = text.rsplit("=", 1)[-1]
    return text.strip("\"'`").rstrip(".,;:)!?").replace("\\", "/")


def is_path_claim(text):
    """True when this token asserts that a specific repo file exists."""
    if not text or " " in text or "/" not in text:
        return False
    if not _TOKEN.fullmatch(text):
        return False
    if text.startswith(("http", "/", "~", "-")):
        return False
    head, _, tail = text.partition("/")
    # "5000/api/openapi.json" is the tail of a localhost URL, not a path.
    if head.isdigit():
        return False
    basename = tail.split("/")[-1] if tail else ""
    if "." not in basename:
        return False
    return basename.rsplit(".", 1)[-1].lower() in SOURCE_EXTENSIONS


def is_excused(surface_rel, reference):
    if reference in ILLUSTRATIVE_PATHS:
        return True
    if reference.startswith(GENERATED_PREFIXES):
        return True
    return (surface_rel, reference) in DELIBERATELY_ABSENT


def reference_resolves(reference, surface):
    if reference.startswith(("../", "./")):
        return (surface.parent / reference).resolve().is_file()
    if "*" in reference:
        pattern = re.compile(
            "^"
            + re.escape(reference)
            .replace(r"\*\*", "\x00")
            .replace(r"\*", "[^/]*")
            .replace("\x00", ".*")
            + "$"
        )
        return any(pattern.match(known) for known in PATH_INDEX)
    if reference in PATH_INDEX:
        return True
    return (surface.parent / reference).is_file()


def iter_path_claims(surface):
    """Yield (line number, normalized path) for every path claim in one surface."""
    in_fence = False
    text = surface.read_text(encoding="utf-8", errors="replace")
    for lineno, line in enumerate(text.splitlines(), 1):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            raws = [match.group(0) for match in _TOKEN.finditer(line)]
        else:
            raws = [
                match.group(1)
                for match in list(_CODE_SPAN.finditer(line))
                + list(_LINK_TARGET.finditer(line))
            ]
        for raw in raws:
            reference = normalize_reference(raw)
            if is_path_claim(reference):
                yield lineno, reference


def scan_for_broken_paths(surfaces=None):
    """Return [(surface, line, path)] for every unexcused, unresolvable claim."""
    broken = []
    for surface in instruction_surfaces() if surfaces is None else surfaces:
        try:
            surface_rel = surface.relative_to(REPO_ROOT).as_posix()
        except ValueError:  # a planted file outside the repo, used by the meta-tests
            surface_rel = surface.name
        for lineno, reference in iter_path_claims(surface):
            if is_excused(surface_rel, reference):
                continue
            if not reference_resolves(reference, surface):
                broken.append((surface_rel, lineno, reference))
    return broken


class TestInstructionPathsExist:
    def test_no_instruction_file_names_a_missing_path(self):
        broken = scan_for_broken_paths()
        assert not broken, (
            "Instruction files reference paths that do not exist:\n"
            + "\n".join(f"  {surface}:{line} -> {ref}" for surface, line, ref in broken)
        )

    def test_scan_actually_examines_paths(self):
        """Guard the guard: a scan that inspects nothing can never fail."""
        examined = sum(len(list(iter_path_claims(s))) for s in instruction_surfaces())
        assert examined > 300, (
            "Only %d path claims extracted. The extractor has stopped matching -- "
            "a green run below this threshold means nothing." % examined
        )

    def test_planted_bad_path_is_caught(self, tmp_path):
        """Guard the guard: prove a missing path is actually reported."""
        planted = tmp_path / "planted.md"
        planted.write_text(
            "Run the game with `src/game.py` as documented.\n", encoding="utf-8"
        )
        assert [ref for _, _, ref in scan_for_broken_paths([planted])] == ["src/game.py"]

    def test_planted_bad_path_in_a_fence_is_caught(self, tmp_path):
        """Fenced command blocks are where ``python src/game.py`` actually lived."""
        planted = tmp_path / "planted_fence.md"
        planted.write_text(
            "```bash\npython tests/api/test_validators.py\n```\n", encoding="utf-8"
        )
        assert [ref for _, _, ref in scan_for_broken_paths([planted])] == [
            "tests/api/test_validators.py"
        ]

    def test_real_path_is_not_reported(self, tmp_path):
        """The complement: a guard that flags everything is equally useless."""
        planted = tmp_path / "planted_ok.md"
        planted.write_text(
            "See `src/secure_pickle.py` and `tools/run_api.py`.\n", encoding="utf-8"
        )
        assert scan_for_broken_paths([planted]) == []

    def test_suffix_reference_is_not_reported(self, tmp_path):
        """A path written relative to a prefix the prose established is fine."""
        planted = tmp_path / "planted_suffix.md"
        planted.write_text("Under frontend/src/: `hooks/useApi.js`.\n", encoding="utf-8")
        assert scan_for_broken_paths([planted]) == []

    def test_no_unused_excuses(self):
        """Every DELIBERATELY_ABSENT entry must still describe a real gap.

        Without this the list becomes a graveyard: someone fixes a doc, the excuse
        stays behind, and the next stale reference to the same path is swallowed
        silently. Delete the entry when you fix the doc.
        """
        surfaces = {
            s.relative_to(REPO_ROOT).as_posix(): s for s in instruction_surfaces()
        }
        stale = []
        for (surface_rel, reference), _reason in DELIBERATELY_ABSENT.items():
            surface = surfaces.get(surface_rel)
            if surface is None:
                stale.append("%s is no longer an instruction surface" % surface_rel)
            elif reference_resolves(reference, surface):
                stale.append("%s -> %s now exists" % (surface_rel, reference))
            elif not any(ref == reference for _, ref in iter_path_claims(surface)):
                stale.append("%s no longer mentions %s" % (surface_rel, reference))
        assert not stale, "Stale DELIBERATELY_ABSENT entries -- delete them:\n" + "\n".join(
            "  " + line for line in stale
        )


# ---------------------------------------------------------------------------
# Guard 2: prose enumerations of norecursedirs must match pytest.ini
# ---------------------------------------------------------------------------
#
# Narrower and blunter than the path guard, aimed at one measured defect: five
# instruction sites listed ``tests/api`` among the excluded directories after
# pytest.ini had stopped excluding it, so agents kept "restoring" an exclusion
# that had been deliberately removed.
#
# Prose is not parsed for meaning. An enumeration is located structurally: a run
# of directory tokens joined only by separators (comma, "and", slash, quotes,
# whitespace). A run naming two or more genuinely-excluded directories is taken to
# BE the exclusion list, and its ``tests/*`` members must then match pytest.ini's
# exactly. Surrounding prose cannot confuse it, because a directory mentioned
# outside such a run forms its own run of one and is ignored.

_DIR_TOKEN = re.compile(r"(?:tests/[a-z_0-9]+|\.claude)/?")
_ENUM_RUN = re.compile(
    r"(?:%s)(?:(?:\s*(?:,|and|/|&)\s*|\s+)(?:%s))+"
    % (_DIR_TOKEN.pattern, _DIR_TOKEN.pattern)
)


def pytest_ini_norecursedirs():
    text = (REPO_ROOT / "pytest.ini").read_text(encoding="utf-8")
    match = re.search(r"^norecursedirs\s*=\s*(.+)$", text, re.MULTILINE)
    assert match, "pytest.ini has no norecursedirs setting"
    return {entry.strip().rstrip("/") for entry in match.group(1).split()}


def find_exclusion_enumerations(text, real_excluded):
    """Return [(line, {dirs})] for each run that enumerates the exclusion set.

    Scans blank-line-separated blocks with their lines joined, not single lines:
    markdown wraps prose at ~90 columns, so a four-item exclusion list routinely
    straddles two lines. A line-at-a-time checker sees two short runs instead of
    one full one and silently stops enforcing -- which it did, on this repo's own
    coverage dashboard, the first time it ran.
    """
    found = []
    lineno = 1
    for block in re.split(r"\n[ \t]*\n", text):
        joined = " ".join(block.splitlines()).replace("`", " ")
        for run in _ENUM_RUN.finditer(joined):
            named = {token.rstrip("/") for token in _DIR_TOKEN.findall(run.group(0))}
            if len(named & real_excluded) >= 2:
                found.append((lineno, named))
        lineno += block.count("\n") + 2
    return found


class TestNorecursedirsProseMatchesPytestIni:
    def test_every_prose_exclusion_list_matches(self):
        real = pytest_ini_norecursedirs()
        real_tests = {d for d in real if d.startswith("tests/")}
        mismatches = []
        for surface in instruction_surfaces():
            text = surface.read_text(encoding="utf-8", errors="replace")
            for lineno, named in find_exclusion_enumerations(text, real):
                # `.claude` is not a test directory; docs may omit it.
                named_tests = {d for d in named if d.startswith("tests/")}
                if named_tests != real_tests:
                    rel = surface.relative_to(REPO_ROOT).as_posix()
                    mismatches.append(
                        "  %s:%d lists %s, pytest.ini excludes %s"
                        % (rel, lineno, sorted(named_tests), sorted(real_tests))
                    )
        assert not mismatches, (
            "Prose disagrees with pytest.ini's norecursedirs:\n" + "\n".join(mismatches)
        )

    def test_tests_api_is_excluded_and_prose_says_why(self):
        """tests/api is excluded ON PURPOSE, and the reason travels with it.

        This assertion has been both ways round. It was briefly "tests/api must
        NOT be excluded", on the premise that an excluded directory rots -- true
        of the contents, false of the exclusion, which exists because building a
        real session mutates module-level item and merchant registries and
        pollutes downstream shop and spawn tests. What makes the exclusion safe
        is not that it is written down but that the directory still RUNS, one
        process per file, in its own CI job. So both halves are asserted: the
        exclusion, and the job that redeems it.
        """
        assert "tests/api" in pytest_ini_norecursedirs()
        workflow = (
            REPO_ROOT / ".github" / "workflows" / "api-tests.yml"
        ).read_text(encoding="utf-8")
        assert "tests/api" in workflow, (
            "tests/api is excluded from the default suite and no CI workflow "
            "walks it -- that is the state the exclusion was removed to fix"
        )
        ini = (REPO_ROOT / "pytest.ini").read_text(encoding="utf-8")
        assert "api-tests.yml" in ini, (
            "pytest.ini excludes tests/api without pointing at the job that "
            "runs it, which is how the directory went uncovered before #522"
        )

    def test_stale_enumeration_is_caught(self):
        """Guard the guard: the pre-fix prose must still fail this checker."""
        real = pytest_ini_norecursedirs()
        stale = (
            "backend default suite (excludes tests/broken, tests/uat, "
            "tests/integration)"
        )
        found = find_exclusion_enumerations(stale, real)
        assert found, "checker no longer recognises an exclusion enumeration at all"
        assert any("tests/api" not in named for _, named in found)

    def test_current_enumeration_is_accepted(self):
        real = pytest_ini_norecursedirs()
        good = (
            "excludes `tests/api`, `tests/broken`, `tests/uat` and "
            "`tests/integration`"
        )
        found = find_exclusion_enumerations(good, real)
        assert found, "checker fails to recognise a correct enumeration"
        for _, named in found:
            assert {d for d in named if d.startswith("tests/")} == {
                d for d in real if d.startswith("tests/")
            }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
