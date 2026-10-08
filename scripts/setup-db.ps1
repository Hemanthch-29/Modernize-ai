# setup-db.ps1 — create/reset ShopDB on (localdb)\MSSQLLocalDB via sqlcmd.
$ErrorActionPreference = 'Stop'
$initSql = Join-Path $PSScriptRoot '..\sample-legacy\database\init.sql'

Write-Host 'Starting LocalDB instance MSSQLLocalDB...'
sqllocaldb start MSSQLLocalDB | Out-Null

Write-Host "Running init.sql ($initSql)..."
sqlcmd -S '(localdb)\MSSQLLocalDB' -E -b -i $initSql
if ($LASTEXITCODE -ne 0) { throw "init.sql failed with exit code $LASTEXITCODE" }

Write-Host 'ShopDB is ready.' -ForegroundColor Green
