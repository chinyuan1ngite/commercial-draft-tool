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
& .venv\Scripts\python.exe -m pip install -e .
& .venv\Scripts\python.exe -m draft_tool.launcher --smoke-test
Write-Host "Install completed. Run the launcher.bat file."
