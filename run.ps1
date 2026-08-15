$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot

$ComfyPython = Join-Path $ProjectRoot "runtime\ComfyUI\.venv\Scripts\python.exe"
$ComfyRoot = Join-Path $ProjectRoot "runtime\ComfyUI"
try {
    Invoke-RestMethod "http://127.0.0.1:8188/system_stats" -TimeoutSec 2 | Out-Null
} catch {
    if (-not (Test-Path -LiteralPath $ComfyPython)) {
        throw "ComfyUI runtime is missing: $ComfyPython"
    }
    Start-Process -FilePath $ComfyPython -WorkingDirectory $ComfyRoot -WindowStyle Hidden `
        -ArgumentList @("main.py", "--disable-auto-launch", "--listen", "127.0.0.1", "--port", "8188") `
        -RedirectStandardOutput (Join-Path $ComfyRoot "comfyui.out.log") `
        -RedirectStandardError (Join-Path $ComfyRoot "comfyui.err.log")
    $Ready = $false
    for ($Attempt = 0; $Attempt -lt 90; $Attempt++) {
        Start-Sleep -Seconds 1
        try {
            Invoke-RestMethod "http://127.0.0.1:8188/system_stats" -TimeoutSec 2 | Out-Null
            $Ready = $true
            break
        } catch { }
    }
    if (-not $Ready) { throw "ComfyUI did not become ready on port 8188." }
}
python app.py --config config.yaml
