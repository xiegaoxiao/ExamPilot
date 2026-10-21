[CmdletBinding()]
param(
    [switch]$InitDemo,
    [switch]$Install,
    [switch]$Rebuild,
    [ValidateRange(1024,65535)][int]$Port = 8000,
    [string]$HomePath
)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$env:PYTHONUTF8 = '1'
if ($HomePath) { $env:EXAMPILOT_HOME = [System.IO.Path]::GetFullPath($HomePath) }

function Assert-ExitCode([string]$Step) {
    if ($LASTEXITCODE -ne 0) { throw "$Step failed (exit $LASTEXITCODE)." }
}

$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
$newEnvironment = -not (Test-Path -LiteralPath $pythonExe)
if ($newEnvironment) {
    & python -c "import sys; assert sys.version_info >= (3, 11), 'Python 3.11+ is required'"
    Assert-ExitCode 'Python version check'
    & python -m venv .venv
    Assert-ExitCode 'Create Python environment'
}
$dependencyStamp = Join-Path $projectRoot '.venv\exampilot-dependencies.sha256'
$lockFile = Join-Path $projectRoot 'backend\requirements.lock.txt'
$dependencyHash = (Get-FileHash -LiteralPath $lockFile -Algorithm SHA256).Hash
$installedHash = if (Test-Path -LiteralPath $dependencyStamp) { (Get-Content -LiteralPath $dependencyStamp -Raw).Trim() } else { '' }
if ($Install -or $newEnvironment -or $installedHash -ne $dependencyHash) {
    & $pythonExe -m pip install -r $lockFile
    Assert-ExitCode 'Install Python dependencies'
    Set-Content -LiteralPath $dependencyStamp -Value $dependencyHash -Encoding utf8
}

$frontendRoot = Join-Path $projectRoot 'frontend'
$nodeModules = Join-Path $frontendRoot 'node_modules'
$distIndex = Join-Path $frontendRoot 'dist\index.html'
Push-Location -LiteralPath $frontendRoot
try {
    $needNode = $Install -or -not (Test-Path -LiteralPath $nodeModules)
    if ($needNode) {
        & npm.cmd ci
        Assert-ExitCode 'Install frontend dependencies'
    }
    $sourcesChanged = $false
    if (Test-Path -LiteralPath $distIndex) {
        $builtAt = (Get-Item -LiteralPath $distIndex).LastWriteTimeUtc
        $sourcesChanged = [bool](Get-ChildItem -LiteralPath (Join-Path $frontendRoot 'src') -Recurse -File | Where-Object LastWriteTimeUtc -GT $builtAt | Select-Object -First 1)
    }
    if ($Rebuild -or $Install -or $needNode -or $sourcesChanged -or -not (Test-Path -LiteralPath $distIndex)) {
        & npm.cmd run build
        Assert-ExitCode 'Type-check and build frontend'
    }
} finally { Pop-Location }

& $pythonExe backend/manage.py init
Assert-ExitCode 'Database migration'
if ($InitDemo) {
    & $pythonExe backend/manage.py demo
    Assert-ExitCode 'Initialize original demo (not published)'
}
Write-Host "ExamPilot: http://127.0.0.1:$Port" -ForegroundColor Cyan
Write-Host 'Press Ctrl+C to stop. PDF files and attempt history are preserved.'
& $pythonExe -m uvicorn backend.app.main:app --host 127.0.0.1 --port $Port
Assert-ExitCode 'ExamPilot server'
