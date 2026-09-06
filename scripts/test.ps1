$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (Test-Path ".venv\Scripts\python.exe") {
  & .venv\Scripts\python.exe -m compileall -q src tests
  & .venv\Scripts\python.exe -m unittest discover -s tests -v
} else {
  & python -m compileall -q src tests
  & python -m unittest discover -s tests -v
}
