$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonLauncher -and -not $python) { throw "Python 3.11+ not found. Install it from python.org and enable Add to PATH." }

if (-not (Test-Path ".venv\Scripts\python.exe")) {
  if ($pythonLauncher) { & $pythonLauncher.Source -3 -m venv .venv }
  else { & $python.Source -m venv .venv }
}
& .venv\Scripts\python.exe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed (exit code $LASTEXITCODE)." }
& .venv\Scripts\python.exe -m pip install -e .
if ($LASTEXITCODE -ne 0) { throw "Project installation failed (exit code $LASTEXITCODE)." }
& .venv\Scripts\python.exe -m pip check
if ($LASTEXITCODE -ne 0) { throw "Dependency check failed (exit code $LASTEXITCODE)." }
& .venv\Scripts\python.exe scripts/check_version.py
if ($LASTEXITCODE -ne 0) { throw "Version consistency check failed (exit code $LASTEXITCODE)." }
$hadDraftHome = Test-Path Env:DRAFT_TOOL_HOME
$previousDraftHome = $env:DRAFT_TOOL_HOME
try {
  $env:DRAFT_TOOL_HOME = Join-Path $PWD ".local/install-smoke"
  & .venv\Scripts\python.exe -m draft_tool.launcher --smoke-test
  if ($LASTEXITCODE -ne 0) { throw "Launcher smoke test failed (exit code $LASTEXITCODE)." }
} finally {
  if ($hadDraftHome) { $env:DRAFT_TOOL_HOME = $previousDraftHome }
  else { Remove-Item Env:DRAFT_TOOL_HOME -ErrorAction SilentlyContinue }
}
Write-Host "Install completed. Run the launcher.bat file."
