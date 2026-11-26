$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
if (!(Test-Path "logs")) { New-Item -ItemType Directory -Path "logs" | Out-Null }
$env:PYTHONIOENCODING = "utf-8"
while ($true) {
  $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  $listening = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
  if ($listening) {
    Start-Sleep -Seconds 10
    continue
  }
  Add-Content -Path "logs\server_watchdog.log" -Value "[$ts] Starting MAS AI Agents server..."
  & python app.py --no-browser *>> "logs\server_stdout.log"
  $code = $LASTEXITCODE
  $ts2 = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  Add-Content -Path "logs\server_watchdog.log" -Value "[$ts2] Server exited code=$code. Restarting in 3s..."
  Start-Sleep -Seconds 3
}
