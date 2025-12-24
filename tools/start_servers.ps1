# Start Backend Server
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& { .venv\Scripts\Activate.ps1; python tools/run_api.py }"

# Start Frontend Server
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& { cd frontend; npm install; npm run dev }"

Write-Host "Servers are starting in separate windows..."
