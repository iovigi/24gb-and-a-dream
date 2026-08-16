$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot

# ComfyUI is started by the application itself (see comfyui.autostart in
# config.yaml), so the packaged executable and this script behave identically.

$LogDir = Join-Path $ProjectRoot "logs"
if (-not (Test-Path -LiteralPath $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
$LauncherLog = Join-Path $LogDir "launcher.log"

# Unbuffered output plus the interpreter-level fault handler, so a native crash
# (access violation in llama.cpp / torch / Qt) still prints a C traceback.
$env:PYTHONUNBUFFERED = "1"
$env:PYTHONFAULTHANDLER = "1"

Add-Content -Path $LauncherLog -Value "===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | launching app.py =====" -Encoding utf8
$ErrorActionPreference = "Continue"
python -X faulthandler app.py --config config.yaml 2>&1 | Tee-Object -FilePath $LauncherLog -Append
$ExitCode = $LASTEXITCODE
Add-Content -Path $LauncherLog -Value "===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | app.py exited with code $ExitCode =====" -Encoding utf8

if ($ExitCode -ne 0) {
    Write-Host ""
    Write-Host "24GB and a Dream exited with code $ExitCode." -ForegroundColor Red
    Write-Host "Logs:" -ForegroundColor Yellow
    Write-Host "  $LogDir\app.log       (central session log)"
    Write-Host "  $LogDir\crash.log     (native faults and unhandled exceptions)"
    Write-Host "  $LogDir\console.log   (raw stdout/stderr)"
    Write-Host "  $LauncherLog (launcher output)"
    Write-Host ""
    Write-Host "--- last 40 lines of crash.log ---" -ForegroundColor Yellow
    $CrashLog = Join-Path $LogDir "crash.log"
    if (Test-Path -LiteralPath $CrashLog) { Get-Content -LiteralPath $CrashLog -Tail 40 }
    Write-Host ""
    Read-Host "Press Enter to close"
}
exit $ExitCode
