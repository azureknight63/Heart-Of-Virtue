<#
.SYNOPSIS
    Deploys Heart of Virtue to nexusfidei.dev/games/HeartOfVirtue.

.PARAMETER Version
    Version tag for this release (e.g. "0.1.0"). Used to name the tarball.
#>
param (
    [Parameter(Mandatory = $true)]
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
$envFile = ".env"
if (Test-Path $envFile) {
    $envContent = Get-Content $envFile
    foreach ($line in $envContent) {
        if ($line -match "NEXUS_PASS\s*=\s*(.*)") {
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
$scpCommand = "scp $tarName ${serverUser}@${serverHost}:${remoteTar}"

if (Get-Command sshpass -ErrorAction SilentlyContinue) {
    sshpass -p $env:NEXUS_PASS $scpCommand
} else {
    Invoke-Expression $scpCommand
}
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

$sshCommand = "ssh ${serverUser}@${serverHost} `"$remoteScript`""

if (Get-Command sshpass -ErrorAction SilentlyContinue) {
    sshpass -p $env:NEXUS_PASS $sshCommand
} else {
    Invoke-Expression $sshCommand
}

if ($LASTEXITCODE -ne 0) { Write-Error "Remote deployment failed"; exit 1 }

# ── 4b. Restart the backend, then verify it actually came up ────────────────
Write-Host "Restarting $serviceName and verifying it stays up..." -ForegroundColor Cyan

# `sleep 3` before is-active: with Type=simple, `systemctl restart` returns as
# soon as the process is forked, so an immediate check would pass for a
# gunicorn that is about to exit on wsgi.py's refusal.
$restartScript = "sudo systemctl restart $serviceName && sleep 3 && " +
"systemctl is-active --quiet $serviceName"

$restartCommand = "ssh ${serverUser}@${serverHost} `"$restartScript`""

if (Get-Command sshpass -ErrorAction SilentlyContinue) {
    sshpass -p $env:NEXUS_PASS $restartCommand
} else {
    Invoke-Expression $restartCommand
}

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
