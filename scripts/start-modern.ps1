# start-modern.ps1 — start FastAPI (:8000) and the Angular UI (:4200), each in its own window.
# See PROJECT_CONTEXT.md sections 6.5 and 6.6. Requires .env (SHOPDB_CONN) and ShopDB on LocalDB.
$root = Split-Path $PSScriptRoot -Parent
$api = Join-Path $root 'migrated\shop-api-python'
$ui = Join-Path $root 'migrated\shop-ui-angular'
$python = Join-Path $root '.venv\Scripts\python.exe'

Write-Host 'Starting FastAPI on http://localhost:8000 ...'
Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$api'; & '$python' -m uvicorn app.main:app --port 8000"

Write-Host 'Starting Angular UI on http://localhost:4200 ...'
Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$ui'; npx ng serve --port 4200 --proxy-config proxy.conf.json"

Write-Host ''
Write-Host 'Modern app starting in two new windows:'
Write-Host '  API: http://localhost:8000'
Write-Host '  UI:  http://localhost:4200'
