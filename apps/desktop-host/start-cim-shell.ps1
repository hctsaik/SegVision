# Launch SegVision UI inside Native App's cim-light.exe (same Tauri shell).
# Does not use segvision-desktop-host.exe.

$ErrorActionPreference = "Stop"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$native = $env:NATIVEAPP_ROOT
if (-not $native) {
  throw "Set NATIVEAPP_ROOT to the Native App repository directory before running this script."
}
$native = (Resolve-Path $native).Path
$python = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "SegVision venv python missing: $python" }

$exeCandidates = @(
  (Join-Path $native "apps\host-tauri\src-tauri\target\debug\cim-light.exe"),
  (Join-Path $native "apps\host-tauri\src-tauri\target\release\cim-light.exe"),
  (Join-Path $native "apps\host-tauri\prebuilt\cim-light.exe")
)
$exe = $exeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $exe) {
  throw @"
cim-light.exe not found. Build Native App shell once:
  cargo build --manifest-path $native\apps\host-tauri\src-tauri\Cargo.toml
Then rerun this script.
"@
}

$secret = [guid]::NewGuid().ToString("N")
$outFile = Join-Path $env:TEMP "segvision-cim-sidecar.out"
$errFile = Join-Path $env:TEMP "segvision-cim-sidecar.err"
$sidecar = Start-Process -FilePath $python -ArgumentList @(
  "-m", "segvision.transport.desktop_api",
  "--secret", $secret,
  "--port", "0",
  "--host", "127.0.0.1",
  "--prefer-real",
  "--dev-origin", "http://localhost:5173"
) -WorkingDirectory $repo -RedirectStandardOutput $outFile -RedirectStandardError $errFile -PassThru -NoNewWindow

$port = $null
$deadline = (Get-Date).AddSeconds(20)
while ((Get-Date) -lt $deadline) {
  if (Test-Path $outFile) {
    $line = Get-Content $outFile -TotalCount 1 -ErrorAction SilentlyContinue
    if ($line) {
      try { $port = (ConvertFrom-Json $line).port } catch { $port = $null }
      if ($port) { break }
    }
  }
  Start-Sleep -Milliseconds 200
}
if (-not $port) { throw "SegVision sidecar did not print a port. See $outFile" }

# The sidecar prints its port before loading MobileSAM. Wait for health before
# opening the native window so a cold CPU model load is not mistaken for the
# fake backend or an unavailable engine by the first UI request.
$healthHeaders = @{
  "X-SegVision-Launch-Secret" = $secret
  "X-SegVision-Protocol-Version" = "1.1"
}
$health = $null
$healthDeadline = (Get-Date).AddSeconds(90)
while ((Get-Date) -lt $healthDeadline) {
  try {
    $health = Invoke-RestMethod -UseBasicParsing "http://127.0.0.1:$port/v1/health" -Headers $healthHeaders -TimeoutSec 3
    if ($health.ready) { break }
  } catch {
    # MobileSAM is still importing/loading, or uvicorn is not listening yet.
  }
  Start-Sleep -Milliseconds 500
}
if (-not $health -or -not $health.ready) {
  throw "SegVision sidecar health timeout while loading the real backend. See $outFile and $errFile"
}
Write-Host "SegVision backend: $($health.backend.name) setup=$($health.setup_state)"

try {
  Invoke-WebRequest -UseBasicParsing "http://localhost:5173/" -TimeoutSec 2 | Out-Null
} catch {
  Start-Process -FilePath "npm" -ArgumentList @("--prefix", (Join-Path $repo "apps\desktop-ui"), "run", "dev") -WorkingDirectory $repo -WindowStyle Hidden
  $viteDeadline = (Get-Date).AddSeconds(40)
  do {
    Start-Sleep -Milliseconds 400
    try {
      Invoke-WebRequest -UseBasicParsing "http://localhost:5173/" -TimeoutSec 2 | Out-Null
      break
    } catch {
      if ((Get-Date) -gt $viteDeadline) { throw "Vite did not start on :5173" }
    }
  } while ($true)
}

$ui = "http://localhost:5173/?host=cim&sidecar=$([uri]::EscapeDataString("http://127.0.0.1:$port"))&secret=$secret"
Write-Host "CIM shell: $exe"
Write-Host "SegVision sidecar: http://127.0.0.1:$port  pid=$($sidecar.Id)"
Write-Host "Webview URL: $ui"

$env:CIM_WEBVIEW_URL = $ui
$env:CIM_WINDOW_TITLE = "SegVision"
$env:CIM_SKIP_ENGINE = "1"
$env:PYTHONUTF8 = "1"
Start-Process -FilePath $exe -WorkingDirectory (Split-Path $exe)
