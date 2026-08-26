# Start Backend Server, Frontend Server, and Log Viewer
# Usage: .\tools\start_servers.ps1 [CONFIG_FILE] [-NoLogcat]
#   e.g. .\tools\start_servers.ps1 config_eastern_descent_test.ini
#   Also opens the condensed debug-log viewer (tools/logcat.py --tail) in its
#   own window. Pass -NoLogcat to skip it.
param([string]$ConfigFile, [switch]$NoLogcat)

$backendCmd = if ($ConfigFile) { "& { .venv\Scripts\Activate.ps1; python tools/run_api.py $ConfigFile }" } else { "& { .venv\Scripts\Activate.ps1; python tools/run_api.py }" }

Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd

# Start Frontend Server
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& { cd frontend; npm install; npm run dev }"

# Start Log Viewer
if (-not $NoLogcat) {
    $logcatCmd = "& { `$host.UI.RawUI.WindowTitle = 'HoV Log Viewer'; .venv\Scripts\Activate.ps1; python tools/logcat.py --tail }"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $logcatCmd
}

Write-Host "Servers are starting in separate windows..."
if ($ConfigFile) { Write-Host "Config: $ConfigFile" }
if (-not $NoLogcat) { Write-Host "Log viewer (tools/logcat.py --tail) is starting in a separate window..." }
