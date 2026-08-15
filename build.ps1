$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot

python -m PyInstaller --noconfirm --clean --windowed --onedir --exclude-module torch --name "24GB and a Dream" app.py

$Distribution = Join-Path $ProjectRoot "dist\24GB and a Dream"
Copy-Item -LiteralPath (Join-Path $ProjectRoot "config.yaml") -Destination $Distribution -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "workflows") -Destination $Distribution -Recurse -Force
New-Item -ItemType Directory -Path (Join-Path $Distribution "models") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $Distribution "projects") -Force | Out-Null

Write-Host "Built: $Distribution\24GB and a Dream.exe"
