param([switch]$Browser)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$pythonPath = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }
function Invoke-ProjectPython {
  param([string[]]$Arguments, [string]$FailureMessage)
  & $script:pythonPath @Arguments
  if ($LASTEXITCODE -ne 0) { throw "$FailureMessage (exit code $LASTEXITCODE)." }
}
$hadBrowserTests = Test-Path Env:DRAFT_BROWSER_TESTS
$previousBrowserTests = $env:DRAFT_BROWSER_TESTS
try {
  if ($Browser) { $env:DRAFT_BROWSER_TESTS = "1" }
  else { Remove-Item Env:DRAFT_BROWSER_TESTS -ErrorAction SilentlyContinue }
  Invoke-ProjectPython @("-m", "pip", "check") "Dependency check failed"
  Invoke-ProjectPython @("scripts/check_version.py") "Version consistency check failed"
  Invoke-ProjectPython @("-m", "compileall", "-q", "src", "tests", "examples", "scripts") "Compilation check failed"
  Invoke-ProjectPython @("-m", "unittest", "discover", "-s", "tests", "-v") "Test suite failed"
} finally {
  if ($hadBrowserTests) { $env:DRAFT_BROWSER_TESTS = $previousBrowserTests }
  else { Remove-Item Env:DRAFT_BROWSER_TESTS -ErrorAction SilentlyContinue }
}
