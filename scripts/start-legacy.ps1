# start-legacy.ps1 — start the .NET API (:5000) and the React UI (:5173), each in its own window.
$root = Split-Path $PSScriptRoot -Parent
$api = Join-Path $root 'sample-legacy\shop-api'
$ui = Join-Path $root 'sample-legacy\shop-ui'

Write-Host 'Starting .NET API on http://localhost:5000 ...'
Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$api'; dotnet run --urls http://localhost:5000"

Write-Host 'Starting React UI on http://localhost:5173 ...'
Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$ui'; npm run dev"

Write-Host ''
Write-Host 'Legacy app starting in two new windows:'
Write-Host '  API: http://localhost:5000'
Write-Host '  UI:  http://localhost:5173'
