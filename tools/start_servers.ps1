# Start Backend Server
# Usage: .\tools\start_servers.ps1 [CONFIG_FILE]
#   e.g. .\tools\start_servers.ps1 config_eastern_descent_test.ini
param([string]$ConfigFile)

$backendCmd = if ($ConfigFile) { "& { .venv\Scripts\Activate.ps1; python tools/run_api.py $ConfigFile }" } else { "& { .venv\Scripts\Activate.ps1; python tools/run_api.py }" }

Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd

# Start Frontend Server
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& { cd frontend; npm install; npm run dev }"

Write-Host "Servers are starting in separate windows..."
if ($ConfigFile) { Write-Host "Config: $ConfigFile" }
