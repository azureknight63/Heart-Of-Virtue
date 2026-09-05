<#
.SYNOPSIS
    Deploys Heart of Virtue to nexusfidei.dev/games/HeartOfVirtue.

.PARAMETER Version
    Version tag for this release (e.g. "0.1.0"). Used to name the tarball.
#>
param (
    # Constrained to the characters a version tag can contain. $Version reaches
    # a tarball name and, before this file was fixed, an Invoke-Expression, so
    # a value like  1.0"; rm -rf ~; "  became a second command. Every remote
    # call below now invokes the executable directly with an argument array, so
    # nothing here is re-parsed as a command line and this pattern is the belt
    # to those braces -- kept because it rejects the value at the boundary
    # where the operator can still see why.
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9A-Za-z.+_-]+$')]
    [string]$Version
)

$serverUser   = "alex"
$serverHost   = "nexusfidei.dev"
$container    = "webserver"
$targetDir    = "/var/www/html/wp-content/HeartOfVirtue"
$appDir       = "/home/alex/heart-of-virtue"
$tarName      = "hov_$Version.tar"
$remoteTar    = "~/hov_dist.tar"

# ── Load NEXUS_PASS from .env ───────────────────────────────────────────────
#
# The pattern is anchored at the start of the line. It used to be
# "NEXUS_PASS\s*=\s*(.*)", which matches anywhere in the line -- so a
# commented-out `# NEXUS_PASS=old-password` matched, and `break` on the first
# hit meant a retired password shadowed the live one further down. That failure
# surfaces as an authentication error against production, saying nothing about
# .env. Commented-out entries are the normal shape of this repo's env files
# (see .env.example, where nearly everything ships commented), so this was not
# a hypothetical line.
$envFile = ".env"
if (Test-Path $envFile) {
    $envContent = Get-Content $envFile
    foreach ($line in $envContent) {
        if ($line -match '^\s*NEXUS_PASS\s*=\s*(.*)$') {
            $env:NEXUS_PASS = $matches[1].Trim()
            break
        }
    }
} else {
    Write-Error ".env file not found!"
    exit 1
}

if (-not $env:NEXUS_PASS) {
    Write-Error "NEXUS_PASS not found in .env"
    exit 1
}

function Invoke-Remote {
    <#
    .SYNOPSIS
        Run ssh/scp, through sshpass when it is available, with real arguments.

    .DESCRIPTION
        Every remote call in this script used to be built as a single command
        STRING and then either handed to `sshpass -p $pass $command` or to
        `Invoke-Expression $command`. Both halves were wrong:

        * PowerShell passes a string as ONE argv element, so sshpass received
          "scp hov_1.0.tar alex@host:~/hov_dist.tar" as the *name of the
          program to execute*. There is no such program. The sshpass path of
          this script cannot ever have worked as written.
        * Invoke-Expression re-parses the string as PowerShell source, which is
          how $Version reached a command line. ($Version is also
          [ValidatePattern]-constrained at the top, but a script should not
          need a validator to be safe from its own variables.)

        Passing an argument ARRAY to a native executable fixes both: PowerShell
        hands each element over as its own argv entry, and nothing is re-parsed
        as code. $remoteScript stays one element -- which is exactly right, as
        it is one argument to ssh, to be interpreted by the *remote* shell.

    .NOTES
        Not tested against the real server from here, and deliberately so; what
        it does is verified only against PowerShell's own argument handling.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    if (Get-Command sshpass -ErrorAction SilentlyContinue) {
        & sshpass -e $Exe @Arguments
    } else {
        # No sshpass: ssh/scp prompt for the password themselves.
        & $Exe @Arguments
    }
}

# sshpass takes the password from the SSHPASS environment variable with -e,
# rather than from argv with -p. `sshpass -p $env:NEXUS_PASS ...` put the
# production SSH password in this process's command line, where any local
# `Get-CimInstance Win32_Process` / `ps` can read it for as long as the call
# runs. The environment is readable by far fewer things and is not echoed.
$env:SSHPASS = $env:NEXUS_PASS

# ── 1. Build frontend ───────────────────────────────────────────────────────
Write-Host "Building frontend..." -ForegroundColor Cyan
Set-Location frontend
npm ci --prefer-offline
if ($LASTEXITCODE -ne 0) { Write-Error "npm ci failed"; exit 1 }
npm run build
if ($LASTEXITCODE -ne 0) { Write-Error "npm run build failed"; exit 1 }
Set-Location ..

# ── 2. Create tarball from dist/ ────────────────────────────────────────────
Write-Host "Creating tarball $tarName..." -ForegroundColor Cyan
tar -cvf $tarName -C frontend/dist .
if ($LASTEXITCODE -ne 0) { Write-Error "tar failed"; exit 1 }

# ── 3. Upload to server ─────────────────────────────────────────────────────
Write-Host "Uploading to $serverHost..." -ForegroundColor Cyan
$scpArgs = @($tarName, "${serverUser}@${serverHost}:${remoteTar}")

Invoke-Remote -Exe "scp" -Arguments $scpArgs
if ($LASTEXITCODE -ne 0) { Write-Error "Upload failed"; exit 1 }

# ── 4. Deploy into container + pull backend + restart Flask ─────────────────
#
# FLASK_ENV=production on the backend is NOT set by this script and NOT set by
# the Procfile. The Procfile's "web:" line carries the variable, but nothing on
# this path reads a Procfile: the backend runs as the systemd unit
# $serviceName, restarted below. FLASK_ENV therefore comes from that unit's
# Environment=/EnvironmentFile=, or from the server's own $appDir/.env (which
# wsgi.py loads with override=False) — all of them on the server, none of them
# in this repo, and none of them visible from here.
#
# What makes that verifiable rather than assumed is wsgi.py: it refuses to boot
# under anything but FLASK_ENV=production (SystemExit, before create_app), so a
# unit missing the variable does not serve a development config — it fails to
# start. "Unit is active after the restart" therefore *is* the proof that
# FLASK_ENV=production reached the process, which is why the restart is its own
# step with its own check below instead of the last clause of the chain above,
# where a failure would have been reported as "Remote deployment failed".
#
# A systemd unit is deliberately not invented here for a machine this script
# cannot inspect.
$serviceName = "heart-of-virtue"

Write-Host "Deploying on server..." -ForegroundColor Cyan

# Construct the remote shell command
$remoteScript = "docker cp $remoteTar ${container}:/tmp/hov_dist.tar && " +
"docker exec $container sh -c 'mkdir -p $targetDir && tar -xf /tmp/hov_dist.tar -C $targetDir' && " +
"docker exec $container sh -c 'rm /tmp/hov_dist.tar' && " +
"docker exec $container sh -c 'find $targetDir -type d -exec chmod 755 {} \;' && " +
"docker exec $container sh -c 'find $targetDir -type f -exec chmod 644 {} \;' && " +
"cd $appDir && git pull origin master && " +
".venv/bin/pip install -q -r requirements.txt -r requirements-api.txt"

Invoke-Remote -Exe "ssh" -Arguments @("${serverUser}@${serverHost}", $remoteScript)

if ($LASTEXITCODE -ne 0) { Write-Error "Remote deployment failed"; exit 1 }

# ── 4b. Restart the backend, then verify it actually came up ────────────────
Write-Host "Restarting $serviceName and verifying it stays up..." -ForegroundColor Cyan

# `sleep 3` before is-active: with Type=simple, `systemctl restart` returns as
# soon as the process is forked, so an immediate check would pass for a
# gunicorn that is about to exit on wsgi.py's refusal.
$restartScript = "sudo systemctl restart $serviceName && sleep 3 && " +
"systemctl is-active --quiet $serviceName"

Invoke-Remote -Exe "ssh" -Arguments @("${serverUser}@${serverHost}", $restartScript)

if ($LASTEXITCODE -ne 0) {
    Write-Error @"
$serviceName is not running after the restart. The frontend has been deployed;
the backend has not come up.

The most likely cause is the one this repo cannot check for you: wsgi.py exits
before building the app unless FLASK_ENV is exactly "production", and that
variable is set on the server -- by the systemd unit or by $appDir/.env --
neither of which is in this repository. Check both:

    systemctl cat $serviceName            # look for Environment=FLASK_ENV=production
                                          # (or an EnvironmentFile= that sets it)
    grep FLASK_ENV $appDir/.env           # the other place it can come from
    journalctl -u $serviceName -n 50      # the refusal message names the value it saw

Other startup failures (a missing SECRET_KEY or ENCRYPTION_KEY in production,
a bad dependency install) surface in the same journal.
"@
    exit 1
}

# ── 5. Cleanup local tarball ────────────────────────────────────────────────
Remove-Item $tarName -ErrorAction SilentlyContinue

Write-Host "Deploy v$Version complete!" -ForegroundColor Green
