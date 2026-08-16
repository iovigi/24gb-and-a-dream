$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot

$SpecFile = Join-Path $ProjectRoot "24GB and a Dream.spec"
$Distribution = Join-Path $ProjectRoot "dist\24GB and a Dream"
$Executable = Join-Path $Distribution "24GB and a Dream.exe"
$LogDir = Join-Path $ProjectRoot "logs"
if (-not (Test-Path -LiteralPath $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
$BuildLog = Join-Path $LogDir "build.log"

# Build from the spec so the conda DLL collection in it is always applied.
# Passing options like --windowed here instead would make PyInstaller
# regenerate the spec and silently drop that fix.
Write-Host "Building from $SpecFile" -ForegroundColor Cyan
$ErrorActionPreference = "Continue"
python -m PyInstaller --noconfirm --clean "$SpecFile" 2>&1 | Tee-Object -FilePath $BuildLog
$BuildExit = $LASTEXITCODE
$ErrorActionPreference = "Stop"

if ($BuildExit -ne 0) {
    throw "PyInstaller failed with exit code $BuildExit. See $BuildLog"
}

# PyInstaller only warns about unresolved DLLs, then produces an executable that
# dies during bootstrap on the user's machine. Treat it as a build failure.
$MissingLibraries = Select-String -Path $BuildLog -Pattern "Library not found: could not resolve" -SimpleMatch
if ($MissingLibraries) {
    Write-Host ""
    Write-Host "Unresolved native dependencies - the packaged app would not start:" -ForegroundColor Red
    $MissingLibraries | ForEach-Object { Write-Host "  $($_.Line.Trim())" }
    Write-Host ""
    Write-Host "Add the matching glob to CONDA_DLL_PATTERNS in '24GB and a Dream.spec'." -ForegroundColor Yellow
    throw "Build aborted: $($MissingLibraries.Count) unresolved DLL dependencies."
}

# Runtime assets stay outside the bundle so they can be edited after deployment.
Copy-Item -LiteralPath (Join-Path $ProjectRoot "workflows") -Destination $Distribution -Recurse -Force
New-Item -ItemType Directory -Path (Join-Path $Distribution "projects") -Force | Out-Null

# Relative paths in config.yaml resolve against the folder holding that file, so
# a plain copy would make the packaged app look for runtime/ and models/ next to
# the executable, where they are not (they are tens of gigabytes). Point the
# generated config at this machine's copies instead; projects/ and workflows/
# stay relative so they live with the deployment.
python "$(Join-Path $ProjectRoot 'tools\make_dist_config.py')" `
    --source "$(Join-Path $ProjectRoot 'config.yaml')" `
    --output "$(Join-Path $Distribution 'config.yaml')"
if ($LASTEXITCODE -ne 0) { throw "Failed to generate the packaged config.yaml" }

# Prove the packaged app actually starts: imports, Qt plugins, config, window.
# A bootstrap failure shows a modal dialog and hangs, so a timeout is a failure.
Write-Host ""
Write-Host "Running packaged self-test..." -ForegroundColor Cyan
$SelfTest = Start-Process -FilePath $Executable -ArgumentList "--selftest" -PassThru
try {
    Wait-Process -Id $SelfTest.Id -Timeout 120 -ErrorAction Stop
} catch {
    try { $SelfTest.Kill() } catch { }
    throw "Self-test hung for 120s - the packaged app is showing a startup error dialog. See $Distribution\logs\ and $BuildLog"
}
if ($SelfTest.ExitCode -ne 0) {
    $PackagedLog = Join-Path $Distribution "logs\app.log"
    if (Test-Path -LiteralPath $PackagedLog) {
        Write-Host "--- last 30 lines of the packaged app log ---" -ForegroundColor Yellow
        Get-Content -LiteralPath $PackagedLog -Tail 30
    }
    throw "Self-test failed with exit code $($SelfTest.ExitCode)."
}

Write-Host ""
Write-Host "Self-test passed." -ForegroundColor Green
Write-Host "Built: $Executable"
