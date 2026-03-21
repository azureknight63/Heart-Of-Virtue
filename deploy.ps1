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
Write-Host "Deploying on server..." -ForegroundColor Cyan

# Construct the remote shell command
$remoteScript = "docker cp $remoteTar ${container}:/tmp/hov_dist.tar && " +
"docker exec $container sh -c 'mkdir -p $targetDir && tar -xf /tmp/hov_dist.tar -C $targetDir' && " +
"docker exec $container sh -c 'rm /tmp/hov_dist.tar' && " +
"docker exec $container sh -c 'find $targetDir -type d -exec chmod 755 {} \;' && " +
"docker exec $container sh -c 'find $targetDir -type f -exec chmod 644 {} \;' && " +
"cd $appDir && git pull origin master && " +
".venv/bin/pip install -q -r requirements.txt -r requirements-api.txt && " +
"sudo systemctl restart heart-of-virtue"

$sshCommand = "ssh ${serverUser}@${serverHost} `"$remoteScript`""

if (Get-Command sshpass -ErrorAction SilentlyContinue) {
    sshpass -p $env:NEXUS_PASS $sshCommand
} else {
    Invoke-Expression $sshCommand
}

if ($LASTEXITCODE -ne 0) { Write-Error "Remote deployment failed"; exit 1 }

# ── 5. Cleanup local tarball ────────────────────────────────────────────────
Remove-Item $tarName -ErrorAction SilentlyContinue

Write-Host "Deploy v$Version complete!" -ForegroundColor Green
