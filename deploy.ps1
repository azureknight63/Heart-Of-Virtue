#Requires -Version 7.4
<#
.SYNOPSIS
    Deploys Heart of Virtue to nexusfidei.dev/games/HeartOfVirtue behind a
    maintenance page, or reports what the server is running.

.DESCRIPTION
    Four modes, the deploy with a -KeepMaintenance variant. Runbook, rollback commands and caveats:
    docs/development/deployment.md

      .\deploy.ps1                       Full deploy. Build, upload, stage the
                                         build next to the live one, raise the
                                         maintenance page, replace + restart the
                                         backend, prove it answers, promote the
                                         staged build, prove the web server
                                         serves it, and lift the page, which is
                                         the last step.
      .\deploy.ps1 -KeepMaintenance      The same, minus the lift: the page
                                         stays up, and a private preview URL
                                         loads the new build for a test on
                                         production. Lift later by hand.
      .\deploy.ps1 -Status               Drift report: the server's backend
                                         commit vs origin/master and vs the
                                         live frontend's, the served bundle,
                                         service and maintenance state.
                                         Read-only on the server; locally it
                                         only fetches origin/master.
      .\deploy.ps1 -Maintenance On|Off   Toggle the maintenance page by hand.
      .\deploy.ps1 -DryRun               Print every remote script the deploy
                                         would run. No build, no network, no
                                         credential needed.

    Every remote phase is a bash script RENDERED by a New-*Script function and
    handed to ssh as one argument. The rendering is what tests/test_deploy_script.py
    exercises (it dot-sources this file), which is why nothing below runs at
    top level except when the file is executed rather than dot-sourced.

    FLASK_ENV=production is NOT set here. wsgi.py refuses to boot under any
    other value, so "the service is active and /health answers" after the
    restart is the proof that the server's own unit or .env carries it.

    7.4 is the floor on purpose: from 7.3 native arguments containing `"` reach
    ssh.exe escaped (the remote scripts are full of them), and from 7.4
    Invoke-WebRequest refuses an HTTPS->HTTP redirect.

.PARAMETER Version
    Version tag for this release. Defaults to the VERSION file. Names the
    tarball only; the deployed commit is whatever origin/master is.

.PARAMETER Status
    Drift report. Needs the ssh password; read-only on the server, and
    locally it only fetches origin/master.

.PARAMETER Maintenance
    On or Off. Raises the maintenance page (uploading this checkout's
    frontend/public/maintenance.html) or lifts it by restoring the index a
    raise, a stopped deploy or a -KeepMaintenance deploy saved; Off also
    deletes any preview-*.html a -KeepMaintenance deploy left.

.PARAMETER KeepMaintenance
    Full deploy that does not lift. Everything up to and including the proof
    that the web server serves the new bundle is unchanged; then, instead of
    the lift, the new build's real index stays parked behind the page and a
    copy of it is placed at preview-<32 random hex>.html in the live
    directory. The deploy prints that preview URL: it boots the new build
    for whoever holds it, while every other URL still shows the page. A
    reload or a sign-out lands on the page again; reopen the preview URL.
    Lift with -Maintenance Off, which also deletes the preview. A deploy
    over a kept build is refused until it is lifted or rolled back.
    Combines with -DryRun; not with -Status or -Maintenance.

.PARAMETER DryRun
    Prints the plan and every remote script the deploy would run. No build,
    no network, no credential.

.PARAMETER EnvFile
    Where NEXUS_PASS (the SSH password for the server) is read from. Defaults
    to .env beside this script. Only used when sshpass is installed; without
    it, ssh and scp prompt for the password themselves.
#>
param (
    # The value reaches a tarball name. The same literal is checked again in
    # Main, because PowerShell does not validate a DEFAULT value (here, the
    # VERSION file); a test holds the two literals equal.
    [ValidatePattern('\A[0-9A-Za-z.+_-]+\z')]
    [string]$Version = (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'VERSION') -Raw).Trim(),

    [switch]$Status,

    [ValidateSet('On', 'Off')]
    [string]$Maintenance,

    [switch]$KeepMaintenance,

    [switch]$DryRun,

    [string]$EnvFile = (Join-Path $PSScriptRoot '.env')
)

# ── server layout ───────────────────────────────────────────────────────────
$ServerUser   = 'alex'
$ServerHost   = 'nexusfidei.dev'
$ServerLogin  = "$ServerUser@$ServerHost"
$Container    = 'webserver'
$LiveDir      = '/var/www/html/wp-content/HeartOfVirtue'
$StagingDir   = "$LiveDir.new"
$PreviousDir  = "$LiveDir.prev"
$AppDir       = "/home/$ServerUser/heart-of-virtue"
$ServiceName  = 'heart-of-virtue'
$BackendPort  = 5000
$RemoteTar    = '~/hov_dist.tar'
$ContainerTar = '/tmp/hov_dist.tar'
$RemotePage   = '~/hov_maintenance.html'
$PublicBase   = 'https://nexusfidei.dev/games/HeartOfVirtue'
$PublicApiUrl = "$PublicBase/api/info"
$LocalHealthUrl = "http://127.0.0.1:$BackendPort/health"
# How the server installs the backend's dependencies, in the checkout. The
# printed rollback runs it against an EARLIER commit, so it must only name
# files every commit has.
$BackendInstallCommand = '.venv/bin/pip install -q -r requirements.txt -r requirements-api.txt'

# ── local build ─────────────────────────────────────────────────────────────
$FrontendDir  = 'frontend'
$PublicDir    = "$FrontendDir/public"
$DistDir      = "$FrontendDir/dist"
$TarName      = "hov_$Version.tar"
# --include=dev: with NODE_ENV=production in the environment npm would skip
# the devDependencies the build is made of.
$BuildSteps   = @(
    @{ Exe = 'npm'; Arguments = @('ci', '--prefer-offline', '--include=dev') },
    @{ Exe = 'npm'; Arguments = @('run', 'build') }
)
$PackArguments = @('-cf', $TarName, '-C', $DistDir, '.')

# ── names both sides of the deploy agree on ─────────────────────────────────
# The page itself, as Vite copies it from frontend/public/ into the build.
$MaintenancePageFile = 'maintenance.html'
# The attribute that page carries on <html>; how the scripts, -Status and the
# public checks tell the page from the app.
$MaintenanceMarker   = 'data-hov-maintenance'
# A build's real index while the maintenance page fronts it (staged, promoted).
$ParkedIndex         = 'index.html.parked'
# The live directory's real index while a raise has replaced it.
$SavedIndex          = 'index.html.pre-maintenance'
# Every build carries the commit it was built from, so a rollback can name the
# backend that matches the frontend it restores.
$CommitFile          = '.hov-commit'
# The main entry chunk Vite names in index.html. ERE, so the same text works
# for .NET's -match and for `grep -oE` on the server.
$MainChunkPattern    = 'assets/index-[A-Za-z0-9_-]+\.js'
# A full commit id. \A..\z, not ^..$: .NET's $ also matches before a final
# newline, and this guards text that reaches a sudo command.
$FullShaPattern      = '\A[0-9a-f]{40}\z'
# What /api/info names itself (src/api/app.py, the `info` route).
$ApiName             = 'Heart of Virtue API'
# A -KeepMaintenance deploy's private door: a copy of the real index under
# preview-<token>.html in the live directory. The token is 128 random bits in
# lowercase hex (New-PreviewToken); the pattern admits 16 to 64 hex digits and
# nothing else, because the name lands in the remote script. The glob is how
# the server finds every preview (a kept deploy's marker, and what -Maintenance
# Off deletes); no file the build ships may match it.
$PreviewTokenPattern = '\A[0-9a-f]{16,64}\z'
$PreviewGlob         = 'preview-*.html'
# The states a stopped deploy can leave production in (Write-StuckHelp).
# Kept is not a failure: a -KeepMaintenance deploy ends there on purpose.
$DeployStates        = @('NotRaised', 'Raised', 'Promoted', 'Foreign', 'Lifted', 'Unknown', 'Kept')

# ── budgets ─────────────────────────────────────────────────────────────────
# Backend restart: settle, then poll /health. Worst case before the stage
# gives up: settle + attempts x timeout + (attempts - 1) x delay; -DryRun
# prints it.
$RestartSettleSeconds = 3
$HealthAttempts       = 10
$HealthTimeoutSeconds = 5
$HealthDelaySeconds   = 2
# Public checks from this machine.
$PublicRequestTimeoutSeconds = 30
$PublicRedirectLimit         = 3
$PublicIndexAttempts         = 6
$PublicIndexDelaySeconds     = 5
$PreLiftProbeTimeoutSeconds  = 10
# Public requests from the server itself (reachability, the new bundle).
$ServerPublicTimeoutSeconds  = 15
# How much of a remote or web response a message quotes.
$RemoteTextPreviewLength     = 200

# Raising the page over the live index, shared by the deploy and -Maintenance
# On. The live index is saved first unless a save already exists or the index
# already IS the page: saving the page over the real index is how a lift ends
# up "restoring" the maintenance page. The save and the copy are chained, so
# a failed save never lets the copy overwrite the only real index. __PAGE__ is
# the page to copy in and is not in $RemoteValues, so every template that
# embeds __RAISE__ passes it.
$RaiseFragment = 'cd __LIVE__ && { [ -f __SAVED__ ] || grep -q __MARKER__ index.html || cp index.html __SAVED__; } && cp __PAGE__ index.html'

$RemoteValues = @{
    LIVE                  = $LiveDir
    STAGING               = $StagingDir
    PREVIOUS              = $PreviousDir
    APP                   = $AppDir
    SERVICE               = $ServiceName
    CONTAINER             = $Container
    REMOTE_TAR            = $RemoteTar
    CONTAINER_TAR         = $ContainerTar
    REMOTE_PAGE           = $RemotePage
    PUBLIC_BASE           = $PublicBase
    HEALTH_URL            = $LocalHealthUrl
    INSTALL               = $BackendInstallCommand
    MARKER                = $MaintenanceMarker
    PARKED                = $ParkedIndex
    SAVED                 = $SavedIndex
    COMMIT_FILE           = $CommitFile
    PREVIEW_GLOB          = $PreviewGlob
    CHUNK_PATTERN         = $MainChunkPattern
    RAISE                 = $RaiseFragment
    SETTLE_SECONDS        = $RestartSettleSeconds
    HEALTH_ATTEMPTS       = $HealthAttempts
    HEALTH_TIMEOUT        = $HealthTimeoutSeconds
    HEALTH_DELAY          = $HealthDelaySeconds
    REDIRECT_LIMIT        = $PublicRedirectLimit
    SERVER_PUBLIC_TIMEOUT = $ServerPublicTimeoutSeconds
}

# Values used as the target of rm -rf / mv / tar -C, or as the cwd of
# `git reset --hard`: an absolute path of plain components, or the rendering
# refuses.
$AbsolutePathKeys = @('LIVE', 'STAGING', 'PREVIOUS', 'APP', 'CONTAINER_TAR')

# ── remote scripts ──────────────────────────────────────────────────────────
#
# Single-quoted here-strings: bash's `$(...)` and `$var` would otherwise be
# PowerShell subexpressions. Placeholders are __NAME__ and are expanded from
# $RemoteValues; an unexpanded one is a bug and Expand-Template says so.
#
# The scripts are bash (`set -o pipefail`) and ssh hands them to the login
# shell of $ServerUser, which must therefore be bash. The exit code is the
# failure signal. Each script prints HOV_PHASE=<name> first; each probe prints
# its own `HOV_NAME=value` marker once: NONE for a value looked for and not
# found, UNKNOWN when the probe itself could not run, `yes`/`no` for yes/no.
# HOV_ERROR=<reason> carries a human-readable reason; nothing parses it.

function Expand-Template {
    <#
    .SYNOPSIS
        Fill a remote-script template's __NAME__ placeholders.

    .DESCRIPTION
        Values come from $RemoteValues, overridden by -Values. A value may
        itself contain placeholders (__RAISE__ does), so replacement runs up
        to $maxPasses times, enough for one level of nesting and a pass that
        changes nothing. Refuses to render: an empty or whitespace value; a
        control character in any value (a newline splits the command it lands
        in); a single quote in any value (they are spliced into
        `sh -c '...'`); for a key in $AbsolutePathKeys, anything but a plain
        absolute path; and a carriage return left in the template. `rm -rf `
        on a truncated path is not a script this function produces.

        The template's CRLF line endings become LF first. A here-string keeps
        the line endings of the file it is written in, and a Windows checkout
        (core.autocrlf=true) has this file in CRLF. ssh delivers every `\r`
        to the remote bash, and no phase survives one: `set -euo pipefail\r`
        is an invalid option, which stops a `set -e` phase before its first
        command, and `then\r` is not `then`, a syntax error for the rest.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$Template,
        [hashtable]$Values = @{}
    )
    $all = $RemoteValues.Clone()
    foreach ($key in $Values.Keys) { $all[$key] = $Values[$key] }
    foreach ($key in $all.Keys) {
        $value = [string]$all[$key]
        if ([string]::IsNullOrWhiteSpace($value)) {
            throw "Remote script value $key is empty or whitespace"
        }
        if ($value -cmatch '[\x00-\x1F\x7F-\x9F]') {
            throw "Remote script value $key contains a control character; a newline would split the command it lands in"
        }
        if ($value.Contains("'")) {
            throw "Remote script value $key contains a single quote; values are spliced into sh -c '...'"
        }
        # One or more `/component`s of plain characters, none of them `.` or
        # `..`: no `//`, no trailing slash, no climbing out of the tree.
        if ($key -in $AbsolutePathKeys -and ($value -cnotmatch '\A(/[A-Za-z0-9._+-]+)+\z' -or $value -cmatch '(\A|/)\.\.?(/|\z)')) {
            throw "Remote script value $key must be a plain absolute path, got '$value'"
        }
    }

    $maxPasses = 3
    $out = $Template.Replace("`r`n", "`n")
    $settled = $false
    for ($pass = 0; $pass -lt $maxPasses; $pass++) {
        $before = $out
        foreach ($key in $all.Keys) { $out = $out.Replace("__${key}__", [string]$all[$key]) }
        if ($out -ceq $before) { $settled = $true; break }
    }
    if (-not $settled) {
        throw "Remote script placeholders nest deeper than $maxPasses passes can expand"
    }
    if ($out -cmatch '__[A-Z0-9_]+__') {
        throw "Unexpanded placeholder in remote script: $($Matches[0])"
    }
    # The values were checked above, so a `\r` here came from the template.
    if ($out.Contains("`r")) {
        throw 'Remote script template contains a carriage return outside a CRLF line ending; bash would read it as part of a word'
    }
    return $out
}

function New-StageScript {
    <#
    .SYNOPSIS
        ssh call #1: stage the build, raise maintenance, replace the backend.

    .DESCRIPTION
        Order is the contract. Everything that can be done without players
        noticing happens first: the refusals (a previous deploy's unlifted
        promote; a live directory that cannot be renamed; a host that cannot
        reach its own public URL, which the swap will need), the record of
        what is running (the live build's commit, whether a page is already
        up, the backend's HEAD), the backend preflight (fetch, and proof the
        target commit exists), and the staging of the build beside the live
        one, stamped with its commit. The staged build fronts ITSELF with the
        maintenance page (its real index is parked) so the directory swap
        later cannot lift maintenance by accident.

        Then the window: the page goes up on the live directory, and only then
        does a byte of the running backend change. The backend is pinned to
        the commit the frontend was built from, not pulled; tracked edits and
        local commits on the server are discarded, because the commit is the
        source of truth. The restart is proven by is-active AND by /health
        answering: with Type=simple, `systemctl restart` returns as soon as
        the process forks, and is-active alone passes for a gunicorn about to
        exit on wsgi.py's refusal.
    #>
    param([Parameter(Mandatory = $true)][ValidateScript({ $_ -cmatch $FullShaPattern })][string]$Sha)

    $template = @'
set -euo pipefail
echo "HOV_PHASE=stage"

# 0. Refusals, before anything changes. A parked index in the live directory
#    means a previous deploy promoted and did not lift: it stopped before the
#    lift, or it kept the page up on purpose (-KeepMaintenance, which leaves
#    a preview copy beside it). Either way .prev is then the last build
#    players had, and this run's promote would delete it. Fail closed: a
#    docker failure here aborts rather than reads as "no".
parked=$(docker exec __CONTAINER__ sh -c 'if [ ! -e __LIVE__/__PARKED__ ]; then echo no; elif ls __LIVE__/__PREVIEW_GLOB__ >/dev/null 2>&1; then echo kept; else echo yes; fi')
if [ "$parked" = kept ]; then
  echo "HOV_REFUSED=KEPT_FOR_PREVIEW"
  echo "HOV_ERROR=a -KeepMaintenance deploy is behind the page, waiting for its private test"
  exit 1
fi
if [ "$parked" != no ]; then
  echo "HOV_REFUSED=UNLIFTED_PROMOTE"
  echo "HOV_ERROR=__LIVE__/__PARKED__ exists: a previous deploy stopped after promoting"
  exit 1
fi
# The promote renames the live directory, which a mount point refuses (field 5
# of mountinfo is the mount point).
if docker exec __CONTAINER__ awk -v p=__LIVE__ '$5 == p { f = 1 } END { exit !f }' /proc/self/mountinfo; then
  echo "HOV_REFUSED=LIVE_IS_MOUNTPOINT"
  exit 1
fi
# The swap proves the new bundle through the public URL, from here.
if ! curl -sS -o /dev/null --proto =https --max-time __SERVER_PUBLIC_TIMEOUT__ __PUBLIC_BASE__/; then
  echo "HOV_REFUSED=HOST_CANNOT_REACH_PUBLIC"
  exit 1
fi

# 1. What is running, for the rollback line, and the backend preflight.
#    Reads and a fetch; nothing that is running changes.
live_commit=$(docker exec __CONTAINER__ sh -c 'cat __LIVE__/__COMMIT_FILE__ 2>/dev/null || echo NONE')
echo "HOV_LIVE_COMMIT=$live_commit"
page_was_up=$(docker exec __CONTAINER__ sh -c 'if [ -f __LIVE__/__SAVED__ ] || grep -q __MARKER__ __LIVE__/index.html 2>/dev/null; then echo yes; else echo no; fi')
echo "HOV_PAGE_WAS_UP=$page_was_up"
cd __APP__
prev_sha=$(git rev-parse HEAD)
echo "HOV_PREV_SHA=$prev_sha"
git fetch --quiet origin master
git cat-file -e "__SHA__^{commit}"

# 2. Stage the build inside the container, beside the live directory.
docker cp __REMOTE_TAR__ __CONTAINER__:__CONTAINER_TAR__
rm -f __REMOTE_TAR__
docker exec __CONTAINER__ sh -c 'rm -rf __STAGING__ && mkdir -p __STAGING__ && tar -xf __CONTAINER_TAR__ -C __STAGING__ && rm -f __CONTAINER_TAR__ && chmod -R u=rwX,go=rX __STAGING__ && echo __SHA__ > __STAGING__/__COMMIT_FILE__'
docker exec __CONTAINER__ sh -c 'if [ ! -f __PAGE__ ]; then echo "HOV_ERROR=the maintenance page is missing from the build"; exit 1; fi; mv __STAGING__/index.html __STAGING__/__PARKED__ && cp __PAGE__ __STAGING__/index.html'

# 3. The window opens: maintenance ON for the live directory. The marker is
#    printed by the branch that raised it; a first deploy has nothing to front.
docker exec __CONTAINER__ sh -c 'if [ -f __LIVE__/index.html ]; then __RAISE__ && echo "HOV_MAINTENANCE=ON"; else echo "HOV_MAINTENANCE=NO_LIVE_INDEX"; fi'

# 4. Backend: the same commit the frontend was built from. -q: the commit
#    subject stays off the marker stream.
cd __APP__
git reset -q --hard __SHA__
__INSTALL__

# 5. Restart, then prove it is up AND answering.
sudo systemctl restart __SERVICE__
sleep __SETTLE_SECONDS__
systemctl is-active --quiet __SERVICE__ || { echo "HOV_BACKEND_HEALTH=INACTIVE"; exit 1; }
for attempt in $(seq __HEALTH_ATTEMPTS__); do
  if curl -fsS --max-time __HEALTH_TIMEOUT__ __HEALTH_URL__ >/dev/null; then
    echo "HOV_BACKEND_HEALTH=OK"
    exit 0
  fi
  if [ "$attempt" -lt __HEALTH_ATTEMPTS__ ]; then sleep __HEALTH_DELAY__; fi
done
echo "HOV_BACKEND_HEALTH=FAIL"
exit 1
'@
    return Expand-Template -Template $template -Values @{ SHA = $Sha; PAGE = "$StagingDir/$MaintenancePageFile" }
}

function New-SwapAndLiftScript {
    <#
    .SYNOPSIS
        ssh call #2: promote the staged build, prove it is served, lift.

    .DESCRIPTION
        Runs only after the caller has confirmed from OUTSIDE that an API
        answers through the public URL. The staged build must be the one THIS
        run built (-Chunk) before anything moves, so a tarball from another
        run is never promoted in its place; the check repeats after the
        promote for the race. The previous build is kept as .prev with its
        real index restored, so rollback is a delete and a rename.

        The new chunk is fetched through the PUBLIC URL, HTTPS only, and its
        content type is checked as well as its status: the SPA fallback
        answers a missing asset with index.html and HTTP 200. The lift is one
        rename and the last thing that changes anything.

        With -PreviewToken (a -KeepMaintenance deploy) steps 1 and 2 are the
        same text; step 3 is replaced. Nothing lifts: the real index stays
        parked, and a COPY of it is placed at preview-<token>.html, after
        the served bundle is proven, as the last thing that changes
        anything. The SPA boots from that URL because its router has the
        base as basename and a catch-all route, and its assets are absolute
        under the base. -Maintenance Off lifts later and deletes the copy.
    #>
    param(
        [Parameter(Mandatory = $true)][ValidateScript({ $_ -cmatch "\A$MainChunkPattern\z" })][string]$Chunk,
        [ValidateScript({ $_ -cmatch $PreviewTokenPattern })][string]$PreviewToken
    )

    $prove = @'
set -euo pipefail
echo "HOV_PHASE=swap"

# 1. Promote the staged build -- only if it is this run's -- and keep the
#    previous one restorable. Chained with &&: were the first rename to fail,
#    a `;` would let the second move the staged build INTO the live directory
#    and report success. If the second rename fails, the first is undone. That
#    restores the state this step started from; it does not roll back.
docker exec __CONTAINER__ sh -c '[ "$(grep -oE "__CHUNK_PATTERN__" __STAGING__/__PARKED__ | head -n 1)" = __CHUNK__ ] || { echo "HOV_NEW_CHUNK=MISMATCH (staged)"; exit 1; }; rm -rf __PREVIOUS__ && { [ ! -d __LIVE__ ] || mv __LIVE__ __PREVIOUS__; } && { mv __STAGING__ __LIVE__ || { [ ! -d __PREVIOUS__ ] || mv __PREVIOUS__ __LIVE__; exit 1; }; }'
echo "HOV_PROMOTED=yes"
docker exec __CONTAINER__ sh -c 'if [ -f __PREVIOUS__/__SAVED__ ]; then mv __PREVIOUS__/__SAVED__ __PREVIOUS__/index.html; fi'

# 2. Prove the web server serves THIS run's bundle, via the public URL.
chunk=$(docker exec __CONTAINER__ sh -c 'grep -oE "__CHUNK_PATTERN__" __LIVE__/__PARKED__ | head -n 1')
if [ "$chunk" != "__CHUNK__" ]; then echo "HOV_NEW_CHUNK=MISMATCH (promoted: ${chunk:-NONE})"; exit 1; fi
echo "HOV_NEW_CHUNK=$chunk"
if ! content_type=$(curl -fsSL --proto =https --proto-redir =https --max-redirs __REDIRECT_LIMIT__ --max-time __SERVER_PUBLIC_TIMEOUT__ -o /dev/null -w '%{content_type}' "__PUBLIC_BASE__/__CHUNK__" | tr -d '\r\n'); then
  echo "HOV_ASSET_SERVED=HTTP_ERROR"
  exit 1
fi
case "$content_type" in
  *javascript*) echo "HOV_ASSET_SERVED=OK" ;;
  *) echo "HOV_ASSET_SERVED=WRONG_TYPE ($content_type)"; exit 1 ;;
esac
'@
    $lift = @'
# 3. Lift: the real index goes live in one rename.
docker exec __CONTAINER__ sh -c 'mv __LIVE__/__PARKED__ __LIVE__/index.html'
echo "HOV_MAINTENANCE=OFF"
'@
    $keep = @'
# 3. Keep the page up (-KeepMaintenance): the real index stays parked, and a
#    copy of it under an unguessable name is the operator's private way in.
#    -Maintenance Off lifts later and deletes the copy.
docker exec __CONTAINER__ sh -c 'cp __LIVE__/__PARKED__ __LIVE__/__PREVIEW__'
echo "HOV_PREVIEW=__PREVIEW__"
echo "HOV_MAINTENANCE=KEPT"
'@
    # A here-string drops the newline before its closing '@: the blank line
    # between steps 2 and 3 is put back here, as LF (Expand-Template
    # normalises the here-strings' own line endings).
    if ($PSBoundParameters.ContainsKey('PreviewToken')) {
        return Expand-Template -Template ($prove + "`n`n" + $keep) -Values @{ CHUNK = $Chunk; PREVIEW = "preview-$PreviewToken.html" }
    }
    return Expand-Template -Template ($prove + "`n`n" + $lift) -Values @{ CHUNK = $Chunk }
}

function New-PreviewToken {
    <#
    .SYNOPSIS
        A -KeepMaintenance deploy's preview token: 128 bits from the OS's
        cryptographic generator, as 32 lowercase hex digits. The preview URL
        is the only thing keeping the new build private, so not Get-Random.
    #>
    return [Convert]::ToHexString([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(16)).ToLowerInvariant()
}

function New-StatusScript {
    <#
    .SYNOPSIS
        Read-only: what the server is running. Nothing here mutates.
    #>
    $template = @'
# Deliberately no `set -e`: a report prints every line it can, and each
# probe degrades to a value instead of aborting the ones after it.
set -uo pipefail
echo "HOV_PHASE=status"
echo "HOV_STATUS_HOST_CURL=$(command -v curl >/dev/null 2>&1 && echo yes || echo no)"
if cd __APP__ 2>/dev/null; then
  echo "HOV_STATUS_BACKEND_SHA=$(git rev-parse HEAD 2>/dev/null || echo UNKNOWN)"
  echo "HOV_STATUS_BACKEND_DESCRIBE=$(git log -1 --format='%h %ad %s' --date=short 2>/dev/null || echo UNKNOWN)"
  # --no-optional-locks: a plain `git status` refreshes the index, a write.
  if dirty=$(git --no-optional-locks status --porcelain --untracked-files=no 2>/dev/null); then
    echo "HOV_STATUS_BACKEND_DIRTY=$(printf '%s' "$dirty" | grep -c .)"
  else
    echo "HOV_STATUS_BACKEND_DIRTY=UNKNOWN"
  fi
else
  echo "HOV_STATUS_BACKEND_SHA=NONE"
  echo "HOV_STATUS_BACKEND_DESCRIBE=NONE"
  echo "HOV_STATUS_BACKEND_DIRTY=NONE"
fi
echo "HOV_STATUS_SERVICE=$(systemctl is-active __SERVICE__)"
# HTTP status codes only, never a body: a body is not a marker. 000 is no answer.
echo "HOV_STATUS_LOCAL_HEALTH=$(curl -s -o /dev/null -w '%{http_code}' --max-time __HEALTH_TIMEOUT__ __HEALTH_URL__)"
echo "HOV_STATUS_HOST_REACHES_PUBLIC=$(curl -s -o /dev/null -w '%{http_code}' --proto =https --max-time __SERVER_PUBLIC_TIMEOUT__ __PUBLIC_BASE__/)"
# The real index behind the page if one is up, else the served one. grep's
# argument order is the priority: parked, then saved, then index.html.
chunk=$(docker exec __CONTAINER__ sh -c 'cd __LIVE__ 2>/dev/null && grep -ohE "__CHUNK_PATTERN__" __PARKED__ __SAVED__ index.html 2>/dev/null | head -n 1')
echo "HOV_STATUS_DEPLOYED_CHUNK=${chunk:-NONE}"
echo "HOV_STATUS_LIVE_COMMIT=$(docker exec __CONTAINER__ sh -c 'cat __LIVE__/__COMMIT_FILE__ 2>/dev/null || echo NONE' || echo UNKNOWN)"
echo "HOV_STATUS_PREVIOUS_COMMIT=$(docker exec __CONTAINER__ sh -c 'cat __PREVIOUS__/__COMMIT_FILE__ 2>/dev/null || echo NONE' || echo UNKNOWN)"
echo "HOV_STATUS_MAINTENANCE=$(docker exec __CONTAINER__ sh -c 'if grep -q __MARKER__ __LIVE__/index.html 2>/dev/null; then echo ON; else echo OFF; fi' || echo UNKNOWN)"
echo "HOV_STATUS_UNLIFTED_PROMOTE=$(docker exec __CONTAINER__ sh -c 'test -e __LIVE__/__PARKED__ && echo yes || echo no' || echo UNKNOWN)"
# A -KeepMaintenance deploy's private door, so a lost preview URL can be found.
preview=$(docker exec __CONTAINER__ sh -c 'cd __LIVE__ 2>/dev/null && ls __PREVIEW_GLOB__ 2>/dev/null | head -n 1')
echo "HOV_STATUS_PREVIEW=${preview:-NONE}"
echo "HOV_STATUS_STAGING_PRESENT=$(docker exec __CONTAINER__ sh -c 'test -d __STAGING__ && echo yes || echo no' || echo UNKNOWN)"
echo "HOV_STATUS_PREVIOUS_PRESENT=$(docker exec __CONTAINER__ sh -c 'test -d __PREVIOUS__ && echo yes || echo no' || echo UNKNOWN)"
# Renaming the live directory fails if it is a mount point. Read from the
# container's mount table, whose field 5 is the mount point: a bind mount from
# the same device shares its parent's st_dev, so `stat -c %d` cannot see it.
echo "HOV_STATUS_LIVE_IS_MOUNTPOINT=$(docker exec __CONTAINER__ awk -v p=__LIVE__ '$5 == p { f = 1 } END { print f ? "yes" : "no" }' /proc/self/mountinfo || echo UNKNOWN)"
'@
    return Expand-Template -Template $template
}

function New-MaintenanceOnScript {
    <#
    .SYNOPSIS
        Manual raise. Expects the page uploaded to $RemotePage first.
    #>
    $template = @'
set -euo pipefail
echo "HOV_PHASE=maintenance-on"
docker cp __REMOTE_PAGE__ __CONTAINER__:__PAGE__
rm -f __REMOTE_PAGE__
docker exec __CONTAINER__ sh -c '__RAISE__'
echo "HOV_MAINTENANCE=ON"
'@
    return Expand-Template -Template $template -Values @{ PAGE = "$LiveDir/$MaintenancePageFile" }
}

function New-MaintenanceOffScript {
    <#
    .SYNOPSIS
        Manual lift. Restores whichever real index is waiting: $ParkedIndex
        from a deploy that promoted and did not lift (it stopped before the
        lift, or -KeepMaintenance kept the page up), else $SavedIndex from a
        raise. Refuses to report OFF if what it restored is the page itself.
        Then deletes every preview copy a -KeepMaintenance deploy left, so
        the private door closes when the page lifts.

    .DESCRIPTION
        Parked first: a parked index belongs to the build in the directory
        by construction (only the stage creates one, inside the build it
        parks), while a saved index is a copy of whatever index.html was when
        some raise ran. After a promote the live directory holds no saved
        index at all (the stage's save stays with the previous build, and
        the swap restores it there), so in every state a deploy leaves
        exactly one exists; the order decides only if something else made
        both, and then the directory's own build is the right one to show.
    #>
    $template = @'
set -euo pipefail
echo "HOV_PHASE=maintenance-off"
docker exec __CONTAINER__ sh -c 'cd __LIVE__ && if [ -f __PARKED__ ]; then mv __PARKED__ index.html; elif [ -f __SAVED__ ]; then mv __SAVED__ index.html; else echo "HOV_ERROR=no saved index to restore"; exit 1; fi && if grep -q __MARKER__ index.html; then echo "HOV_ERROR=the restored index is the maintenance page"; exit 1; fi && rm -f __PREVIEW_GLOB__'
echo "HOV_MAINTENANCE=OFF"
'@
    return Expand-Template -Template $template
}

# ── local helpers ───────────────────────────────────────────────────────────
#
# Several helpers return their lines as ONE [string[]] object (`return
# ,[string[]]$x`), so a caller always gets an array: Invoke-Remote,
# Invoke-Git, Get-UnpinnedFiles, Get-UnpinnedEnvironment. Assign the result
# before piping it or wrapping it in @(): `@(f)` wraps the array as a single
# element, and `f | Where-Object` filters the whole array as one item.

function Get-NexusPass {
    <#
    .SYNOPSIS
        NEXUS_PASS from the env file. Throws when the file or the value is
        missing; the caller only asks when sshpass will use it.

    .DESCRIPTION
        Read the way python-dotenv (which reads the same file) reads it: the
        key is case-sensitive and anchored at the start of the line, an
        optional `export ` is allowed, the last definition wins, one pair of
        surrounding quotes is removed (a comment may follow them), and an
        unquoted value loses a trailing ` # comment`. The anchor matters: an
        unanchored pattern once let a commented-out `# NEXUS_PASS=old` shadow
        the live value, which surfaced as an authentication failure against
        production that said nothing about .env. No message here ever quotes
        the value.

        Returned as a value, held in a script variable by the caller, never
        put in $env: -- a process-scope environment variable is inherited by
        every child, and `npm ci` runs every install script in the
        dependency tree. (The file itself is readable by anything running as
        this user; keeping the value out of the environment narrows who is
        handed it, not who could go and read it.)
    #>
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Path not found. It must define NEXUS_PASS (see .env.example)."
    }
    $value = $null
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -cmatch '^\s*(?:export\s+)?NEXUS_PASS\s*=\s*(.*)$') { $value = $Matches[1].Trim() }
    }
    if ($null -eq $value) { throw "NEXUS_PASS not found in $Path" }
    if ($value -cmatch '^([''"])(.*?)\1(?:\s*#.*)?$') {
        $value = $Matches[2]
    } else {
        $value = $value -replace '\s+#.*$', ''
    }
    if (-not $value) { throw "NEXUS_PASS is empty in $Path" }
    return $value
}

function Format-RemoteText {
    <#
    .SYNOPSIS
        Text from the server, the public site or git's remote, made safe to
        print.

    .DESCRIPTION
        Control characters other than tab, and Unicode format characters
        (bidi overrides and the like), become '?', so text in remote output (a
        pip package's, a commit subject's, a web page's, `remote:` lines)
        cannot recolour, reorder, rewrite or write the clipboard of the
        terminal the operator is about to paste sudo commands from. The HOV_*
        markers contain none, so Get-Marker reads the cleaned lines unchanged.
        -MaxLength truncates.
    #>
    param([AllowNull()][AllowEmptyString()][string]$Text, [int]$MaxLength = 0)
    $clean = "$Text" -replace '[\x00-\x08\x0A-\x1F\x7F-\x9F\p{Cf}]', '?'
    if ($MaxLength -gt 0 -and $clean.Length -gt $MaxLength) { $clean = $clean.Substring(0, $MaxLength) + '...' }
    return $clean
}

function Invoke-Remote {
    <#
    .SYNOPSIS
        Run ssh/scp with real arguments; return its output lines as one array.

    .DESCRIPTION
        An argument ARRAY, never a command string: PowerShell hands each
        element to the native executable as its own argv entry and nothing
        is re-parsed as code. The remote script stays one element, which is
        exactly right -- it is one argument to ssh, for the remote shell.
        'Standard' argument passing is pinned here because that one argument
        is full of `"`; the other native calls pass none and keep the
        default.

        The password, when there is one, is $script:NexusPass (set by Main).
        With sshpass present it travels in SSHPASS (`-e`), set around this one
        call and removed in `finally` so it outlives neither the call nor a
        thrown error. `sshpass -p` would put it on this process's command
        line, readable by any local process listing.

        Output is cleaned (Format-RemoteText), echoed as it arrives and also
        returned, so callers can read the HOV_* marker lines the remote
        scripts print. -NoCapture leaves the terminal to the command instead
        (scp's progress meter needs it) and returns nothing. Either way
        $LASTEXITCODE is the native command's, and a non-zero one never
        throws here, whatever the caller's preferences: the deploy decides
        what a failure means, and it must get to print its recovery help.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [switch]$NoCapture
    )
    $PSNativeCommandUseErrorActionPreference = $false
    $PSNativeCommandArgumentPassing = 'Standard'

    $useSshpass = $script:NexusPass -and (Get-Command sshpass -ErrorAction SilentlyContinue)
    $program = $Exe
    $argv = @($Arguments)
    if ($useSshpass) {
        $program = 'sshpass'
        $argv = @('-e', $Exe) + $argv
    }
    $captured = @()
    if ($useSshpass) { $env:SSHPASS = $script:NexusPass }
    try {
        if ($NoCapture) {
            & $program @argv
        } else {
            & $program @argv 2>&1 | ForEach-Object { Format-RemoteText "$_" } | Tee-Object -Variable captured | Out-Host
        }
    } finally {
        if ($useSshpass) { Remove-Item Env:SSHPASS -ErrorAction SilentlyContinue }
    }
    if ($NoCapture) { return }
    return ,[string[]]@($captured | Where-Object { $null -ne $_ })
}

function Invoke-RemoteScript {
    <#
    .SYNOPSIS
        ssh one rendered script; its output lines as one array. ssh's exit
        code is left in $LASTEXITCODE: read it on the very next statement.
    #>
    param([Parameter(Mandatory = $true)][string]$Script)
    return Invoke-Remote -Exe 'ssh' -Arguments @($ServerLogin, $Script)
}

function Send-ToServer {
    <#
    .SYNOPSIS
        scp one file, named relative to this script's directory.

    .DESCRIPTION
        Relative on purpose: a Windows absolute path starts with a drive
        letter and a colon, which is exactly how scp spells a remote host.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    Push-Location -LiteralPath $PSScriptRoot
    try {
        Invoke-Remote -Exe 'scp' -Arguments @($RelativePath, "${ServerLogin}:$Destination") -NoCapture
        if ($LASTEXITCODE -ne 0) { throw "Upload of $RelativePath failed" }
    } finally {
        Pop-Location
    }
}

function Get-Marker {
    <#
    .SYNOPSIS
        The value of the `NAME=value` line a remote script printed, or $null.

    .DESCRIPTION
        Case-sensitive and whole-line. Each marker is printed once, so a name
        seen with two different values means something else's output looked
        like a marker: that returns $null with a warning, because no value is
        safer than the wrong one. (Not "the last one wins" either -- git and
        pip print after some markers.)
    #>
    param([string[]]$Lines, [Parameter(Mandatory = $true)][string]$Name)
    $pattern = "^$([regex]::Escape($Name))=(.*)$"
    $matched = foreach ($line in $Lines) {
        if ($line -cmatch $pattern) { $Matches[1].Trim() }
    }
    $values = @(@($matched) | Select-Object -Unique)
    if ($values.Count -gt 1) {
        Write-Warning "Remote output printed $Name more than once with different values; ignoring it."
        return $null
    }
    if ($values.Count -eq 0) { return $null }
    return $values[0]
}

function Write-Step {
    param([Parameter(Mandatory = $true)][string]$Text)
    Write-Host ''
    Write-Host "── $Text" -ForegroundColor Cyan
}

function Write-PublicLine {
    <#
    .SYNOPSIS
        One aligned line of a public check: the URL, then what it showed.
        Aligned to the API URL, the longest one printed.
    #>
    param([Parameter(Mandatory = $true)][string]$Url, [Parameter(Mandatory = $true)][string]$Text)
    Write-Host "$($Url.PadRight($PublicApiUrl.Length)) $Text"
}

function Format-ShortSha {
    param([string]$Sha)
    if ($Sha -and $Sha.Length -gt 12) { return $Sha.Substring(0, 12) }
    return $Sha
}

function Invoke-Git {
    <#
    .SYNOPSIS
        git in this script's checkout; stdout lines as one array, or a throw
        carrying git's (cleaned) output.
    #>
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    $PSNativeCommandUseErrorActionPreference = $false
    $output = & git -C $PSScriptRoot @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        $detail = ($output | ForEach-Object { Format-RemoteText "$_" }) -join "`n"
        throw "git $($Arguments -join ' ') failed:`n$detail"
    }
    $stdout = @($output | Where-Object { $_ -isnot [System.Management.Automation.ErrorRecord] } | ForEach-Object { "$_" })
    return ,[string[]]$stdout
}

function Get-HeadSha {
    return (Invoke-Git -Arguments @('rev-parse', 'HEAD'))[0]
}

function Get-CheckoutState {
    <#
    .SYNOPSIS
        This checkout's HEAD and origin/master; fetches origin/master first
        unless -NoFetch.

    .DESCRIPTION
        origin/master is resolved as refs/remotes/origin/master: the short
        name would prefer a local tag or branch of the same name, and git's
        "ambiguous" warning goes to stderr, which a successful Invoke-Git
        drops.
    #>
    param([switch]$NoFetch)
    if (-not $NoFetch) { Invoke-Git -Arguments @('fetch', 'origin', 'master', '--quiet') | Out-Null }
    $ids = Invoke-Git -Arguments @('rev-parse', 'HEAD', 'refs/remotes/origin/master')
    return [pscustomobject]@{ Head = $ids[0]; Origin = $ids[1] }
}

function Get-UnpinnedFiles {
    <#
    .SYNOPSIS
        Files that would reach the build but are not what HEAD says.

    .DESCRIPTION
        Modified tracked files anywhere -- the whole repo, not just frontend/,
        because the build reads outside it (vite.config.js reads
        src/resources/csp-policy.json) -- and any file flagged
        --assume-unchanged or --skip-worktree, which `git status` stops
        comparing. Untracked files under frontend/ (Vite bundles src/ and
        copies public/ verbatim). And ignored files that still reach the
        build: anything under frontend/public/, and the env files Vite reads
        in production mode -- .gitignore hides these from `git status`, not
        from `vite build`. Not listed: .env.development (production builds
        never read it) and .env.production (tracked, so the modified check
        covers it).
    #>
    $modified = Invoke-Git -Arguments @('status', '--porcelain', '--untracked-files=no')
    $listing = Invoke-Git -Arguments @('ls-files', '-v')
    # ls-files -v tags: lowercase = assume-unchanged; S = skip-worktree.
    $hidden = @($listing | Where-Object { $_ -cmatch '^([a-z]|S) ' })
    $untracked = Invoke-Git -Arguments @('ls-files', '--others', '--exclude-standard', '--', $FrontendDir)
    $ignored = Invoke-Git -Arguments @(
        'ls-files', '--others', '--ignored', '--exclude-standard', '--',
        $PublicDir, "$FrontendDir/.env", "$FrontendDir/.env.local", "$FrontendDir/.env.production.local"
    )
    return ,[string[]]@(
        @($modified | ForEach-Object { "tracked:   $_" }) +
        @($hidden | ForEach-Object { "hidden:    $_" }) +
        @($untracked | ForEach-Object { "untracked: $_" }) +
        @($ignored | ForEach-Object { "ignored:   $_" })
    )
}

function Get-UnpinnedEnvironment {
    <#
    .SYNOPSIS
        Environment variables that would reach the build but are not in HEAD.

    .DESCRIPTION
        Vite gives VITE_* variables already in the environment priority over
        every .env file, and bakes them into the bundle (the API base URL is
        one). NODE_ENV other than exactly `production` builds development
        React (Vite and React compare case-sensitively). NODE_OPTIONS can load
        code into every node process of the build. Any of them, left over in
        the operator's shell, ships unpinned.
    #>
    $names = @(Get-ChildItem Env: | Where-Object {
        $_.Name -like 'VITE_*' -or $_.Name -eq 'NODE_OPTIONS' -or ($_.Name -eq 'NODE_ENV' -and $_.Value -cne 'production')
    } | ForEach-Object { "environment: $($_.Name)" })
    return ,[string[]]$names
}

function Assert-NothingUnpinned {
    $files = Get-UnpinnedFiles
    $environment = Get-UnpinnedEnvironment
    $unpinned = @($files) + @($environment)
    if ($unpinned.Count -gt 0) {
        throw "These would ship in the bundle but are not in HEAD. Commit, discard, move them out of $FrontendDir/ or unset them first:`n$($unpinned -join "`n")"
    }
}

function Assert-CheckoutIsOriginMaster {
    <#
    .SYNOPSIS
        The commit that will be deployed, once it is proven to be the one
        being built.

    .DESCRIPTION
        The frontend is built from THIS checkout; the backend is checked out on
        the server. They are the same code only if this checkout is exactly
        origin/master and nothing outside HEAD can reach the bundle -- so that
        is required, not assumed.
    #>
    $checkout = Get-CheckoutState
    if ($checkout.Head -ne $checkout.Origin) {
        throw "HEAD is $(Format-ShortSha $checkout.Head) but origin/master is $(Format-ShortSha $checkout.Origin). Deploys ship origin/master: check it out (git checkout master; git pull --ff-only) or push first."
    }
    Assert-NothingUnpinned
    return $checkout.Head
}

function Assert-BuiltFrom {
    <#
    .SYNOPSIS
        After the build: HEAD has not moved and nothing unpinned appeared.
        Worktrees share a repository and sessions run concurrently; the
        build takes minutes.
    #>
    param([Parameter(Mandatory = $true)][string]$Sha)
    $head = Get-HeadSha
    if ($head -ne $Sha) {
        throw "HEAD moved from $(Format-ShortSha $Sha) to $(Format-ShortSha $head) during the build. Nothing was uploaded; run the deploy again."
    }
    Assert-NothingUnpinned
}

function Build-Frontend {
    Write-Step 'Building frontend'
    $PSNativeCommandUseErrorActionPreference = $false
    Push-Location -LiteralPath (Join-Path $PSScriptRoot $FrontendDir)
    try {
        foreach ($step in $BuildSteps) {
            $stepArgs = $step.Arguments
            & $step.Exe @stepArgs
            if ($LASTEXITCODE -ne 0) { throw "$($step.Exe) $($stepArgs -join ' ') failed" }
        }
    } finally {
        Pop-Location
    }
    foreach ($required in @('index.html', $MaintenancePageFile)) {
        if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot "$DistDir/$required"))) {
            throw "$DistDir/$required is missing after the build"
        }
    }
}

function Get-LocalMainChunk {
    <# .SYNOPSIS The main chunk the last local build's index names, or $null (no build, or none named). #>
    $index = Join-Path $PSScriptRoot "$DistDir/index.html"
    if (-not (Test-Path -LiteralPath $index)) { return $null }
    if ((Get-Content -LiteralPath $index -Raw) -cmatch $MainChunkPattern) { return $Matches[0] }
    return $null
}

function Send-Build {
    <# .SYNOPSIS Pack the build and upload it; the local tarball never outlives the call. #>
    Write-Step 'Packing'
    $PSNativeCommandUseErrorActionPreference = $false
    Push-Location -LiteralPath $PSScriptRoot
    try {
        tar @PackArguments
        if ($LASTEXITCODE -ne 0) { throw 'tar failed' }
        Write-Step "Uploading to $ServerHost"
        Send-ToServer -RelativePath $TarName -Destination $RemoteTar
    } finally {
        Remove-Item -LiteralPath $TarName -ErrorAction SilentlyContinue
        Pop-Location
    }
}

function Invoke-Public {
    <#
    .SYNOPSIS
        GET a public URL with caching defeated as far as a client can.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$TimeoutSec = $PublicRequestTimeoutSeconds
    )
    $separator = if ($Url.Contains('?')) { '&' } else { '?' }
    return Invoke-WebRequest -Uri "$Url${separator}hov=$([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())" `
        -Headers @{ 'Cache-Control' = 'no-cache'; 'Pragma' = 'no-cache' } `
        -MaximumRedirection $PublicRedirectLimit -TimeoutSec $TimeoutSec -SkipHttpErrorCheck
}

function Get-PublicApiStatus {
    <#
    .SYNOPSIS
        Whether AN API answers through the proxy, the way a player reaches it.

    .DESCRIPTION
        /api/info rather than /health because the SPA itself fetches /api/info
        at startup, so it is known to route through the web server; /health
        lives at the API root and may not.

        This proves the proxy path, not which build answers: /api/info's
        version is a constant. Newness is proven on the server, by /health
        answering after a restart that stopped the old process.
    #>
    try {
        $response = Invoke-Public -Url $PublicApiUrl
    } catch {
        return [pscustomobject]@{ Ok = $false; Detail = "request failed: $(Format-RemoteText $_.Exception.Message -MaxLength $RemoteTextPreviewLength)" }
    }
    if ($response.StatusCode -ne 200) {
        return [pscustomobject]@{ Ok = $false; Detail = "HTTP $($response.StatusCode)" }
    }
    try {
        $body = $response.Content | ConvertFrom-Json
    } catch {
        return [pscustomobject]@{ Ok = $false; Detail = 'body is not JSON' }
    }
    if ($body -is [pscustomobject] -and $body.PSObject.Properties['name'] -and $body.name -ceq $ApiName) {
        return [pscustomobject]@{ Ok = $true; Detail = "HTTP 200, $ApiName" }
    }
    return [pscustomobject]@{ Ok = $false; Detail = "unexpected body: $(Format-RemoteText $response.Content -MaxLength $RemoteTextPreviewLength)" }
}

function Invoke-PublicApiCheck {
    <# .SYNOPSIS Get-PublicApiStatus, reported on one line; returns the status. #>
    $api = Get-PublicApiStatus
    Write-PublicLine -Url $PublicApiUrl -Text "$(if ($api.Ok) { 'OK' } else { 'FAIL' }) — $($api.Detail)"
    return $api
}

function Find-InPublicIndex {
    <#
    .SYNOPSIS
        Whether the public document contains $Needle.

    .DESCRIPTION
        Returns Found, and Problem: the last failed request or non-200
        (cleaned), or $null when the document simply lacked the needle.
        Retries, because a cache in front of the document root can lag a few
        seconds.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$Needle,
        [int]$Attempts = $PublicIndexAttempts,
        [int]$DelaySeconds = $PublicIndexDelaySeconds,
        [int]$TimeoutSec = $PublicRequestTimeoutSeconds
    )
    $problem = $null
    for ($i = 1; $i -le $Attempts; $i++) {
        try {
            $response = Invoke-Public -Url "$PublicBase/" -TimeoutSec $TimeoutSec
            if ($response.StatusCode -ne 200) {
                $problem = "HTTP $($response.StatusCode)"
            } elseif ($response.Content.Contains($Needle)) {
                return [pscustomobject]@{ Found = $true; Problem = $null }
            } else {
                # A 200 without the needle is an answer, not a problem -- and
                # it clears an earlier attempt's failure.
                $problem = $null
            }
        } catch {
            $problem = Format-RemoteText $_.Exception.Message -MaxLength $RemoteTextPreviewLength
        }
        if ($i -lt $Attempts) { Start-Sleep -Seconds $DelaySeconds }
    }
    return [pscustomobject]@{ Found = $false; Problem = $problem }
}

function Get-RollbackTarget {
    <#
    .SYNOPSIS
        The backend commit that matches the frontend a rollback restores, as
        @{ RollbackSha; RollbackNote } for splatting into Stop-Deploy.

    .DESCRIPTION
        The previous frontend is the build that was live when this run began,
        and the stage reports the commit stamped into it (HOV_LIVE_COMMIT).
        A build from before stamping carries none: then the backend's HEAD at
        the start (HOV_PREV_SHA) is used -- but only if no page was already
        up, because a page left up means an earlier run stopped part-way and
        may have moved HEAD to a commit that never went live. Never the commit
        being deployed, and never anything that is not a full commit id: it
        lands in a command the operator pastes with sudo. RollbackNote says,
        in this script's own words, why no commit could be named.
    #>
    param([string[]]$StageOutput, [Parameter(Mandatory = $true)][string]$DeployingSha)
    $live = Get-Marker -Lines $StageOutput -Name 'HOV_LIVE_COMMIT'
    $prev = Get-Marker -Lines $StageOutput -Name 'HOV_PREV_SHA'
    $pageWasUp = Get-Marker -Lines $StageOutput -Name 'HOV_PAGE_WAS_UP'
    if ($live -cmatch $FullShaPattern -and $live -cne $DeployingSha) {
        return @{ RollbackSha = $live; RollbackNote = $null }
    }
    if ($live -ceq $DeployingSha) {
        return @{ RollbackSha = $null; RollbackNote = 'The live frontend was already this commit (a re-deploy), so there is no earlier release to name.' }
    }
    if ($pageWasUp -ceq 'no' -and $prev -cmatch $FullShaPattern -and $prev -cne $DeployingSha) {
        return @{ RollbackSha = $prev; RollbackNote = $null }
    }
    $why = if ($pageWasUp -ceq 'yes') {
        'A maintenance page was already up when this run began, so the backend commit it reported may never have gone live.'
    } elseif ($prev -ceq $DeployingSha) {
        'The server was already on this commit when this run started (a re-run), so it cannot name the one before.'
    } elseif ($live -or $prev) {
        'The commit this deploy reported is not a commit id; it is not repeated here.'
    } else {
        'This run did not get far enough to report the running commit.'
    }
    return @{ RollbackSha = $null; RollbackNote = $why }
}

function Write-StuckHelp {
    <#
    .SYNOPSIS
        What to do next, for the state a deploy stopped in. Prints commands;
        runs none.

    .DESCRIPTION
        States ($DeployStates): NotRaised (players were never sent to the
        page), Raised (page over the previous frontend; the backend may be
        new), Promoted (a promoted build behind the page), Foreign (the build
        behind the page is not this run's), Lifted (page down, public API
        failing), Unknown (a phase was cut off, so the server's state was not
        observed), Kept (a -KeepMaintenance deploy finished: this run's
        build promoted and proven behind the page, on purpose; -PreviewUrl
        is its private way in).

        Frontend and backend move together: every way out keeps players on a
        frontend and a backend from the same commit, and the backend is put
        right -- and seen answering (BACKEND_OK) -- before anything lifts the
        page. $RollbackSha comes from remote output and lands in a command the
        operator pastes with sudo, so it is checked here, at the sink, as well
        as where it was chosen.
    #>
    param(
        [Parameter(Mandatory = $true)][ValidateScript({ $_ -cin $DeployStates })][string]$State,
        [string]$RollbackSha,
        [string]$RollbackNote,
        [string]$PreviewUrl
    )

    $healthPoll = 'ok=; for i in $(seq <ATTEMPTS>); do curl -fsS --max-time <TIMEOUT> -o /dev/null <URL> && { ok=1; break; }; sleep <DELAY>; done; [ -n "$ok" ] && echo BACKEND_OK || echo BACKEND_FAILED'.
        Replace('<ATTEMPTS>', "$HealthAttempts").Replace('<TIMEOUT>', "$HealthTimeoutSeconds").
        Replace('<URL>', $LocalHealthUrl).Replace('<DELAY>', "$HealthDelaySeconds")
    $frontendRollback = "docker exec $Container sh -c 'test -d $PreviousDir && rm -rf $LiveDir && mv $PreviousDir $LiveDir && { [ ! -f $LiveDir/$SavedIndex ] || mv $LiveDir/$SavedIndex $LiveDir/index.html; }'"

    $backendRollbackLines = @()
    if ($RollbackSha -cmatch $FullShaPattern) {
        $backendRollbackLines += '    (on the server) put back the backend that matches the previous frontend:'
        $backendRollbackLines += "    cd $AppDir && git reset --hard $RollbackSha && $BackendInstallCommand && sudo systemctl restart $ServiceName && sleep $RestartSettleSeconds && { $healthPoll; }"
        $backendRollbackLines += '    Go on only if it printed BACKEND_OK.'
    } else {
        if ($RollbackNote) { $backendRollbackLines += "    $RollbackNote" }
        $backendRollbackLines += "    (on the server) find the commit the previous frontend was built from ($PreviousDir/$CommitFile, or the reflog),"
        $backendRollbackLines += '    then reset to it, reinstall and restart as the runbook shows; go on only once /health answers:'
        $backendRollbackLines += "    git -C $AppDir reflog -n 10"
    }
    $goBackFrontend = @(
        '    (on the server) then the previous frontend -- this also lifts the page:',
        "    $frontendRollback"
    )

    $lines = @('')
    switch ($State) {
        'NotRaised' {
            $lines += 'The maintenance page was not raised; players were not sent to it.'
            $lines += 'Nothing players see changed -- unless this was a first deploy (HOV_MAINTENANCE=NO_LIVE_INDEX above),'
            $lines += 'which may have replaced the backend. Then EITHER fix the cause and deploy again (here):'
            $lines += '    .\deploy.ps1'
            $lines += 'OR, if the backend is not healthy, put a working one back:'
            $lines += $backendRollbackLines
        }
        'Raised' {
            $lines += "The maintenance page is UP over the previous frontend. The new build waits in $StagingDir;"
            $lines += 'the backend may be on the new commit, or partway there.'
            $lines += ''
            $lines += 'EITHER fix the cause and deploy again (here) -- safe from this state:'
            $lines += '    .\deploy.ps1'
            $lines += 'OR go back to the previous release, backend first:'
            $lines += $backendRollbackLines
            $lines += '    (here) then lift the page, keeping the previous frontend:'
            $lines += '    .\deploy.ps1 -Maintenance Off'
        }
        'Promoted' {
            $lines += 'The maintenance page is UP. Behind it: a promoted build and a backend on its commit -- this run''s,'
            $lines += "or, after a refusal, an earlier run's. The previous frontend, if there was one, is in $PreviousDir."
            $lines += ''
            $lines += 'EITHER keep it: .\deploy.ps1 -Status (here) names its chunk (HOV_STATUS_DEPLOYED_CHUNK) and shows'
            $lines += "whether /api/info answers; once $PublicBase/<that chunk> loads as JavaScript in a browser, lift (here):"
            $lines += '    .\deploy.ps1 -Maintenance Off'
            $lines += 'OR go back to the previous release, backend first:'
            $lines += $backendRollbackLines
            $lines += $goBackFrontend
        }
        'Foreign' {
            $lines += 'The maintenance page is UP, and the build behind it is NOT the one this run built: another run''s'
            $lines += 'upload was promoted in its place. Do not lift it. Go back to the previous release, backend first:'
            $lines += $backendRollbackLines
            $lines += $goBackFrontend
        }
        'Lifted' {
            $lines += "The page is lifted and players reach the new release, but $PublicApiUrl is failing."
            $lines += ''
            $lines += 'First put the page back up (here):'
            $lines += '    .\deploy.ps1 -Maintenance On'
            $lines += 'Then EITHER fix the cause and deploy again (here):'
            $lines += '    .\deploy.ps1'
            $lines += 'OR go back to the previous release, backend first:'
            $lines += $backendRollbackLines
            $lines += '    (on the server) then the previous frontend -- this lifts the page again:'
            $lines += "    $frontendRollback"
        }
        'Unknown' {
            $lines += 'A phase that changes production was cut off before the server reported its end, so production''s'
            $lines += 'state is not known here: the server may have carried on after the connection dropped.'
            $lines += ''
            $lines += 'First (here), before anything else:'
            $lines += '    .\deploy.ps1 -Status'
            $lines += 'Its HOV_STATUS_MAINTENANCE and HOV_STATUS_UNLIFTED_PROMOTE lines, with the commits it reports, say which'
            $lines += 'row of the red-state table in docs/development/deployment.md you are in. For reference, the backend:'
            $lines += $backendRollbackLines
        }
        'Kept' {
            $lines += 'The maintenance page is UP, on purpose (-KeepMaintenance). Behind it: this run''s build, promoted and'
            $lines += 'proven served, and a backend on its commit. Players still see the page. Your private way in:'
            $lines += "    $(if ($PreviewUrl) { $PreviewUrl } else { "$PublicBase/$PreviewGlob (.\deploy.ps1 -Status names it: HOV_STATUS_PREVIEW)" })"
            $lines += 'A reload or a sign-out lands on the maintenance page again: reopen the preview URL to get back in.'
            $lines += 'Anyone holding that URL reaches the new build, and the API is not behind the page at all.'
            $lines += ''
            $lines += 'EITHER, once the private test passes, lift the page (here) -- this also deletes the preview:'
            $lines += '    .\deploy.ps1 -Maintenance Off'
            $lines += 'OR, if it fails, go back to the previous release, backend first:'
            $lines += $backendRollbackLines
            $lines += $goBackFrontend
            $lines += 'A deploy over this one is refused until it is lifted or rolled back: promoting again would delete'
            $lines += "$PreviousDir, the last release players had."
        }
    }
    if ($State -ceq 'Kept') {
        Write-Host ($lines -join "`n") -ForegroundColor Yellow
        return
    }
    $lines += ''
    $lines += "Diagnose (on the server): ssh $ServerLogin"
    $lines += "    systemctl status $ServiceName; journalctl -u $ServiceName -n 50"
    $lines += "    systemctl cat $ServiceName | grep -i FLASK_ENV; grep FLASK_ENV $AppDir/.env"
    if ($State -ne 'Unknown') {
        $lines += ''
        $lines += 'Then .\deploy.ps1 -Status (here) shows where things stand.'
    }
    Write-Host ($lines -join "`n") -ForegroundColor Yellow
}

function Stop-Deploy {
    <#
    .SYNOPSIS
        Report why the deploy stopped, print the help for its state, exit 1.
        Never returns.

    .DESCRIPTION
        Write-Host, not Write-Error: under an inherited
        $ErrorActionPreference='Stop' a Write-Error terminates on the spot and
        the help -- the one thing needed while the page is up -- never prints.

        Sets $script:StopReported first: `exit` still runs Invoke-Deploy's
        `finally`, which reads the flag so it does not print a second help.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$Reason,
        [Parameter(Mandatory = $true)][ValidateScript({ $_ -cin $DeployStates })][string]$State,
        [string]$RollbackSha,
        [string]$RollbackNote
    )
    $script:StopReported = $true
    Write-Host ''
    Write-Host $Reason -ForegroundColor Red
    Write-StuckHelp -State $State -RollbackSha $RollbackSha -RollbackNote $RollbackNote
    exit 1
}

function Get-PhaseStop {
    <#
    .SYNOPSIS
        Whether a remote phase's result stops the deploy: $null to carry on,
        or @{ State; Reason } for Stop-Deploy.

    .DESCRIPTION
        The state comes from the markers that ARRIVED, checked in this order:
          - exit 0 carries on;
          - a stage refusal changed nothing (UNLIFTED_PROMOTE and
            KEPT_FOR_PREVIEW leave an earlier run's promote in place:
            Promoted; the others NotRaised);
          - a swap that reported its last step (OFF, or KEPT for a
            -KeepMaintenance swap), or a stage that reported
            health OK, finished: $null, whatever the exit code -- the caller
            warns;
          - exit 255 is ssh's own failure (no remote script exits 255): once
            the phase had started (its HOV_PHASE line arrived) the server may
            have carried on without us, so Unknown -- before anything else,
            because a later marker may have been lost;
          - a promoted build that is not this run's: Foreign; this run's:
            Promoted;
          - otherwise nothing was promoted: the window state (-WindowState).
    #>
    param(
        [Parameter(Mandatory = $true)][ValidateSet('stage', 'swap', IgnoreCase = $false)][string]$Phase,
        [string[]]$Output,
        [int]$ExitCode,
        [Parameter(Mandatory = $true)][ValidateSet('Raised', 'NotRaised', IgnoreCase = $false)][string]$WindowState
    )
    if ($ExitCode -eq 0) { return $null }
    $started = (Get-Marker -Lines $Output -Name 'HOV_PHASE') -ceq $Phase
    $refused = if ($Phase -ceq 'stage') { Get-Marker -Lines $Output -Name 'HOV_REFUSED' } else { $null }

    if ($refused -ceq 'UNLIFTED_PROMOTE') {
        return @{ State = 'Promoted'; Reason = 'Refused: a previous deploy promoted its build and stopped before the lift. Its .prev is the last build known to work, and promoting again would delete it. Nothing was changed. Finish that deploy first:' }
    }
    if ($refused -ceq 'KEPT_FOR_PREVIEW') {
        return @{ State = 'Promoted'; Reason = "Refused: a -KeepMaintenance deploy is behind the page, waiting for its private test ($PreviewGlob in the live directory). Promoting over it would move it into .prev and delete the last release players had. Nothing was changed. Lift it once it passes, or go back to the previous release, then deploy again:" }
    }
    if ($refused) {
        $why = switch ($refused) {
            'LIVE_IS_MOUNTPOINT' { "the live directory $LiveDir is a mount point, and the promote renames it" }
            'HOST_CANNOT_REACH_PUBLIC' { "the server cannot reach $PublicBase/ itself, and the swap proves the new bundle through it" }
            default { 'the server refused' }
        }
        return @{ State = 'NotRaised'; Reason = "Refused before anything changed: $why." }
    }
    if ($Phase -ceq 'swap' -and (Get-Marker -Lines $Output -Name 'HOV_MAINTENANCE') -cin 'OFF', 'KEPT') { return $null }
    if ($Phase -ceq 'stage' -and (Get-Marker -Lines $Output -Name 'HOV_BACKEND_HEALTH') -ceq 'OK') { return $null }
    if ($ExitCode -eq 255 -and $started) {
        return @{ State = 'Unknown'; Reason = "The connection dropped during the $Phase phase, after it had started on the server." }
    }
    if ($Phase -ceq 'swap' -and (Get-Marker -Lines $Output -Name 'HOV_PROMOTED') -ceq 'yes') {
        if ("$(Get-Marker -Lines $Output -Name 'HOV_NEW_CHUNK')".StartsWith('MISMATCH')) {
            return @{ State = 'Foreign'; Reason = 'The promoted build is not the one this run built; not lifting.' }
        }
        return @{ State = 'Promoted'; Reason = 'Swap phase failed after the promote, before the lift; see the output above.' }
    }
    $what = if ($Phase -ceq 'stage') { 'Stage phase failed' } else { 'Swap phase failed before the promote' }
    return @{ State = $WindowState; Reason = "$what; see the output above." }
}

# ── modes ───────────────────────────────────────────────────────────────────

function Invoke-DryRun {
    param([Parameter(Mandatory = $true)][string]$Sha, [switch]$KeepMaintenance)
    $build = ($BuildSteps | ForEach-Object { "$($_.Exe) $($_.Arguments -join ' ')" }) -join ' && '
    $chunk = Get-LocalMainChunk
    if (-not $chunk) { $chunk = 'assets/index-DRYRUN.js' }
    $healthBudget = $RestartSettleSeconds + $HealthAttempts * $HealthTimeoutSeconds + ($HealthAttempts - 1) * $HealthDelaySeconds
    Write-Host "DRY RUN — nothing below is executed. Version $Version, commit $Sha." -ForegroundColor Yellow
    Write-Host '(Not checked in a dry run: that HEAD is origin/master, and that no file or environment variable outside HEAD reaches the build. The real deploy refuses otherwise.)'
    Write-Step "Would build: cd $FrontendDir && $build"
    Write-Step "Would pack: tar $($PackArguments -join ' ')"
    Write-Step "Would upload: scp $TarName ${ServerLogin}:$RemoteTar"
    Write-Step "Would run (ssh #1 — stage, maintenance ON, backend; the health poll gives up after at most ${healthBudget}s):"
    Write-Host (New-StageScript -Sha $Sha)
    Write-Step "Would check from here: GET $PublicApiUrl is 200 and names the API; GET $PublicBase/ shows the maintenance page"
    if ($KeepMaintenance) {
        $token = New-PreviewToken
        Write-Step "Would run (ssh #2 — promote, prove served, KEEP the page up; the chunk is the new build's, here $chunk; the preview token is new on every run, here $token):"
        Write-Host (New-SwapAndLiftScript -Chunk $chunk -PreviewToken $token)
        Write-Step "Would not lift, and would skip the post-lift checks. Would print the private preview URL, here $PublicBase/preview-$token.html; lift later with .\deploy.ps1 -Maintenance Off"
        return
    }
    Write-Step "Would run (ssh #2 — promote, prove served, lift; the chunk is the new build's, here $chunk):"
    Write-Host (New-SwapAndLiftScript -Chunk $chunk)
    Write-Step "Would check from here: GET $PublicApiUrl again; GET $PublicBase/ contains the new bundle's chunk name"
}

function Write-DriftReport {
    <#
    .SYNOPSIS
        -Status's comparison of the server's report with this checkout.
    #>
    param([string[]]$StatusOutput, [Parameter(Mandatory = $true)][string]$Origin)
    $serverSha = Get-Marker -Lines $StatusOutput -Name 'HOV_STATUS_BACKEND_SHA'
    $liveCommit = Get-Marker -Lines $StatusOutput -Name 'HOV_STATUS_LIVE_COMMIT'
    $deployedChunk = Get-Marker -Lines $StatusOutput -Name 'HOV_STATUS_DEPLOYED_CHUNK'
    $shown = { param($value) if ($value) { Format-RemoteText $value -MaxLength 60 } else { 'no marker' } }

    Write-Step 'Drift'
    if ($serverSha -cmatch $FullShaPattern) {
        try {
            # --left-right over server...origin: server-only commits first.
            $serverAhead, $serverBehind = (Invoke-Git -Arguments @('rev-list', '--left-right', '--count', "$serverSha...$Origin"))[0] -split '\s+'
            Write-Host "Backend: server $(Format-ShortSha $serverSha) is $serverBehind commit(s) behind and $serverAhead ahead of origin/master $(Format-ShortSha $Origin)"
        } catch {
            Write-Host "Backend: server commit $(Format-ShortSha $serverSha) could not be compared ($(($_.Exception.Message -split "`n")[0]))"
        }
    } else {
        Write-Host "Backend: server commit unknown ($(& $shown $serverSha))"
    }
    if ($liveCommit -cmatch $FullShaPattern -and $serverSha -cmatch $FullShaPattern) {
        Write-Host "Frontend and backend on the same commit: $(if ($liveCommit -ceq $serverSha) { 'yes' } else { "NO (frontend $(Format-ShortSha $liveCommit))" })"
    } else {
        Write-Host "Frontend commit: $(& $shown $liveCommit) (builds from before this script carry none)"
    }
    $localChunk = Get-LocalMainChunk
    if ($localChunk) {
        Write-Host "Frontend: deployed $(& $shown $deployedChunk); last local build $localChunk $(if ($deployedChunk -ceq $localChunk) { '(same)' } else { '(different)' })"
    } else {
        Write-Host "Frontend: deployed $(& $shown $deployedChunk) (no local build in $DistDir to compare; run the deploy or npm run build)"
    }
    # The name reaches the terminal as a URL, so only one of the shape this
    # script creates is repeated.
    $preview = Get-Marker -Lines $StatusOutput -Name 'HOV_STATUS_PREVIEW'
    $previewToken = if ($preview -cmatch '\Apreview-(.+)\.html\z') { $Matches[1] } else { $null }
    $kept = $previewToken -cmatch $PreviewTokenPattern
    if ((Get-Marker -Lines $StatusOutput -Name 'HOV_STATUS_UNLIFTED_PROMOTE') -ceq 'yes') {
        if ($kept) {
            Write-Warning 'A -KeepMaintenance deploy is behind the page, waiting for its private test. The next deploy refuses until it is lifted (-Maintenance Off) or rolled back (see the runbook).'
        } else {
            Write-Warning 'A deploy promoted its build and stopped before the lift. The next deploy refuses until it is lifted (-Maintenance Off) or rolled back (see the runbook).'
        }
    }
    if ($kept) {
        Write-Host "Private preview: $PublicBase/$preview"
    } elseif ($preview -and $preview -cne 'NONE') {
        Write-Warning "The live directory holds a preview file this script would not have named: $(& $shown $preview)"
    }
}

function Invoke-StatusMode {
    <#
    .SYNOPSIS
        The drift report. A failed fetch or a failed server query does not
        stop the sections after it: this is what every stuck deploy's help
        sends the operator to.

    .DESCRIPTION
        The server's report lines are echoed as they arrive and ARE the report
        (service, local health, maintenance, staging/previous, commits, mount
        point, whether the host reaches its own public URL); only the markers
        the drift section compares are parsed here.
    #>
    Write-Step 'Local checkout'
    $checkout = $null
    try {
        $checkout = Get-CheckoutState
    } catch {
        Write-Warning "Could not fetch origin/master; comparing against the last fetched copy. $(Format-RemoteText $_.Exception.Message -MaxLength $RemoteTextPreviewLength)"
        try { $checkout = Get-CheckoutState -NoFetch } catch { Write-Warning "Local checkout unavailable: $(Format-RemoteText $_.Exception.Message -MaxLength $RemoteTextPreviewLength)" }
    }
    if ($checkout) {
        Write-Host "HEAD           $($checkout.Head)"
        Write-Host "origin/master  $($checkout.Origin) $(if ($checkout.Head -eq $checkout.Origin) { '(same)' } else { '(DIFFERENT — a deploy from here would refuse)' })"
    }

    Write-Step "Server ($ServerHost) — read-only"
    $statusOutput = Invoke-RemoteScript -Script (New-StatusScript)
    $serverReached = $LASTEXITCODE -eq 0
    if (-not $serverReached) {
        Write-Warning 'The server query failed; the public checks below still run.'
    } elseif ($checkout) {
        Write-DriftReport -StatusOutput $statusOutput -Origin $checkout.Origin
    }

    Write-Step 'Public'
    Invoke-PublicApiCheck | Out-Null
    $page = Find-InPublicIndex -Needle $MaintenanceMarker -Attempts 1
    $shows = if ($page.Found) { 'MAINTENANCE PAGE' } elseif ($page.Problem) { "unreachable ($($page.Problem))" } else { 'app document' }
    Write-PublicLine -Url "$PublicBase/" -Text $shows

    if (-not $serverReached) { throw 'Status query failed' }
}

function Invoke-MaintenanceMode {
    param([Parameter(Mandatory = $true)][ValidateSet('On', 'Off')][string]$Setting)

    if ($Setting -eq 'On') {
        # Rendered before the upload, so a script that will not render leaves
        # nothing on the server.
        $raiseScript = New-MaintenanceOnScript
        # The file is published at the site root: it must be the page, not a
        # link to something else (scp follows links).
        $relative = "$PublicDir/$MaintenancePageFile"
        $page = Get-Item -LiteralPath (Join-Path $PSScriptRoot $relative)
        if ($page.LinkType) { throw "$relative is a $($page.LinkType); refusing to publish what it points at" }
        if (-not (Get-Content -LiteralPath $page.FullName -Raw).Contains($MaintenanceMarker)) {
            throw "$relative does not carry $MaintenanceMarker; it is not the maintenance page"
        }
        Write-Step 'Uploading the maintenance page'
        Send-ToServer -RelativePath $relative -Destination $RemotePage
        Write-Step 'Raising it'
        Invoke-RemoteScript -Script $raiseScript | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Could not raise the maintenance page' }
    } else {
        Write-Step 'Lifting the maintenance page'
        Invoke-RemoteScript -Script (New-MaintenanceOffScript) | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Could not lift the maintenance page (is one up? .\deploy.ps1 -Status)' }
    }
    Write-Host "Maintenance $Setting." -ForegroundColor Green
}

function Write-PreLiftPageCheck {
    <# .SYNOPSIS Whether players see the page; a warning at most -- the swap proves the bundle itself. #>
    $page = Find-InPublicIndex -Needle $MaintenanceMarker -Attempts 1 -TimeoutSec $PreLiftProbeTimeoutSeconds
    if ($page.Found) {
        Write-PublicLine -Url "$PublicBase/" -Text 'maintenance page is being served'
        return
    }
    $why = if ($page.Problem) { "the request failed ($($page.Problem))" } else { "a cache in front of the document root is serving the old index, or the document root is not $LiveDir" }
    Write-Warning "$PublicBase/ does not show the maintenance page: $why. Continuing: this affects what players saw, not the safety of the swap, which proves the served bundle itself."
}

function Write-PostLiftBundleCheck {
    <# .SYNOPSIS Whether the public index names the new chunk yet; a warning at most -- the lift has happened. #>
    param([Parameter(Mandatory = $true)][string]$Chunk)
    $served = Find-InPublicIndex -Needle $Chunk
    if ($served.Found) {
        Write-PublicLine -Url "$PublicBase/" -Text "serves the new bundle ($Chunk)"
        return
    }
    $why = if ($served.Problem) { "the request failed ($($served.Problem))" } else { 'a cache in front of the document root is the usual reason; check in a browser with a hard reload' }
    Write-Warning "$PublicBase/ does not yet reference $Chunk. The lift happened on the server; $why."
}

function Invoke-Deploy {
    <#
    .SYNOPSIS
        The full deploy.

    .DESCRIPTION
        Everything up to the upload happens before production is touched,
        including rendering both remote scripts, so a local error there never
        leaves a page up. From ssh #1 on, every way out prints help for the
        state production is in: Get-PhaseStop maps each phase's result to a
        state, and Stop-Deploy prints it and exits. Anything that ends the run
        otherwise (an unexpected error, Ctrl+C) prints from the `finally`:
        the Unknown help while a phase is in flight, the last state observed
        otherwise, and after the lift just a note that the release is live.

        -KeepMaintenance sends the kept swap (New-SwapAndLiftScript
        -PreviewToken) instead, with a token made here, and ends in the Kept
        state: its help is the preview URL and the command that lifts. The
        post-lift checks are skipped, because nothing lifted: the public
        index still IS the page.
    #>
    param([switch]$KeepMaintenance)
    $sha = Assert-CheckoutIsOriginMaster
    $release = "v$Version ($(Format-ShortSha $sha))"
    Write-Host "Deploying $release" -ForegroundColor Cyan

    Build-Frontend
    Assert-BuiltFrom -Sha $sha
    $newChunk = Get-LocalMainChunk
    if (-not $newChunk) { throw "$DistDir/index.html names no chunk matching $MainChunkPattern" }
    $stageScript = New-StageScript -Sha $sha
    $swapArguments = @{ Chunk = $newChunk }
    $previewUrl = $null
    if ($KeepMaintenance) {
        $swapArguments.PreviewToken = New-PreviewToken
        $previewUrl = "$PublicBase/preview-$($swapArguments.PreviewToken).html"
    }
    $swapScript = New-SwapAndLiftScript @swapArguments

    Send-Build

    $script:StopReported = $false        # set by Stop-Deploy
    $finished = $false
    $lifted = $false
    $inFlight = $null                    # the phase whose end has not been reported
    $observed = $null                    # the last state production was seen in
    $rollback = @{ RollbackSha = $null; RollbackNote = 'This run did not get far enough to report the running commit.' }
    try {
        Write-Step 'Staging the build, raising maintenance, replacing the backend (ssh #1)'
        $inFlight = 'stage'
        $stageOutput = Invoke-RemoteScript -Script $stageScript
        $stageExit = $LASTEXITCODE
        $inFlight = $null
        $rollback = Get-RollbackTarget -StageOutput $stageOutput -DeployingSha $sha
        $raised = (Get-Marker -Lines $stageOutput -Name 'HOV_MAINTENANCE') -ceq 'ON'
        $windowState = if ($raised) { 'Raised' } else { 'NotRaised' }
        $stop = Get-PhaseStop -Phase 'stage' -Output $stageOutput -ExitCode $stageExit -WindowState $windowState
        if ($stop) { Stop-Deploy @stop @rollback }
        if ($stageExit -ne 0) {
            Write-Warning 'ssh #1 reported the backend healthy and then exited non-zero (a dropped connection is the usual reason). Continuing.'
        }
        $observed = $windowState

        Write-Step 'Confirming from outside'
        $preLiftApi = Invoke-PublicApiCheck
        if (-not $preLiftApi.Ok) {
            $held = if ($raised) { 'Not lifting maintenance.' } else { 'Not promoting.' }
            Stop-Deploy -State $windowState @rollback -Reason "The backend answers on the server but not through the public URL. $held"
        }
        if ($raised) { Write-PreLiftPageCheck }

        $lastStep = if ($KeepMaintenance) { 'keeping maintenance up' } else { 'lifting maintenance' }
        Write-Step "Promoting the build, proving it is served, $lastStep (ssh #2)"
        $inFlight = 'swap'
        $swapOutput = Invoke-RemoteScript -Script $swapScript
        $swapExit = $LASTEXITCODE
        $inFlight = $null
        $stop = Get-PhaseStop -Phase 'swap' -Output $swapOutput -ExitCode $swapExit -WindowState $windowState
        if ($stop) { Stop-Deploy @stop @rollback }
        if ($KeepMaintenance) {
            # Get-PhaseStop carried on, so the swap reported its last step:
            # the copy. Nothing lifted, so there is nothing post-lift to check.
            $observed = 'Kept'
            if ($swapExit -ne 0) {
                Write-Warning 'ssh #2 placed the preview and then exited non-zero (a dropped connection is the usual reason). Continuing.'
            }
            Write-Host ''
            Write-Host "Deploy $release is promoted and proven served; the maintenance page stays up (-KeepMaintenance)." -ForegroundColor Green
            Write-StuckHelp -State 'Kept' -PreviewUrl $previewUrl @rollback
            $finished = $true
            return
        }
        # Get-PhaseStop carries on after a non-zero swap only once the lift was reported.
        if ($swapExit -ne 0) {
            Write-Warning 'ssh #2 lifted the page and then exited non-zero (a dropped connection is the usual reason). Continuing with the post-lift checks.'
        }
        $lifted = $true

        # Both post-lift checks report before either one stops the deploy.
        Write-Step 'Post-lift'
        $postLiftApi = Invoke-PublicApiCheck
        Write-PostLiftBundleCheck -Chunk $newChunk
        if (-not $postLiftApi.Ok) {
            Stop-Deploy -State 'Lifted' @rollback -Reason "Deploy $release is live, but $PublicApiUrl is failing."
        }

        Write-Host ''
        Write-Host "Deploy $release complete." -ForegroundColor Green
        $finished = $true
    } finally {
        if (-not $finished -and -not $script:StopReported) {
            Write-Host ''
            Write-Host 'The deploy was interrupted after it began changing production.' -ForegroundColor Red
            if ($lifted) {
                Write-Host "The page was already lifted: $release is live. .\deploy.ps1 -Status (here) checks it." -ForegroundColor Yellow
            } else {
                $state = if ($inFlight -or -not $observed) { 'Unknown' } else { $observed }
                Write-StuckHelp -State $state -PreviewUrl $previewUrl @rollback
            }
        }
    }
}

function Main {
    if ($Version -cnotmatch '\A[0-9A-Za-z.+_-]+\z') { throw "Version '$Version' is not a version tag; it names the tarball." }
    if ($Status -and $Maintenance) { throw 'Pick one of -Status or -Maintenance.' }
    if ($DryRun -and ($Status -or $Maintenance)) { throw '-DryRun applies to the deploy only.' }
    if ($KeepMaintenance -and ($Status -or $Maintenance)) { throw '-KeepMaintenance applies to the deploy only.' }

    if ($DryRun) {
        Invoke-DryRun -Sha (Get-HeadSha) -KeepMaintenance:$KeepMaintenance
        return
    }

    # Held in a script variable, not $env:, for the reasons in Get-NexusPass.
    # Only needed when sshpass will use it.
    $script:NexusPass = if (Get-Command sshpass -ErrorAction SilentlyContinue) { Get-NexusPass -Path $EnvFile } else { $null }

    if ($Status) { Invoke-StatusMode; return }
    if ($Maintenance) { Invoke-MaintenanceMode -Setting $Maintenance; return }
    Invoke-Deploy -KeepMaintenance:$KeepMaintenance
}

# Dot-sourcing (what the tests do) defines the functions and stops here.
# Running the file, directly or with &, runs Main.
if ($MyInvocation.InvocationName -ne '.') {
    try {
        Main
    } catch {
        Write-Host (Format-RemoteText "$_") -ForegroundColor Red
        exit 1
    }
}
