$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path ".venv\Scripts\python.exe")) { & "$PSScriptRoot\install.ps1" }
# PyInstaller otherwise silently excludes tkinter when Tcl cannot initialize.
& .venv\Scripts\python.exe -c "import tkinter; tkinter.Tcl()"
if ($LASTEXITCODE -ne 0) { throw "Tcl initialization failed; cannot build the launcher in this environment." }
& .venv\Scripts\python.exe -m pip install pyinstaller
& .venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --name Commercial1688DraftTool --onefile --windowed --paths src --collect-submodules draft_tool --collect-all DrissionPage --collect-all bs4 --collect-all PIL --add-data "README.md;." --add-data "docs;docs" src\draft_tool\launcher.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }
$version = (Get-Content VERSION -Raw).Trim()
$releaseName = "Commercial1688DraftTool-$version-win64"
$releaseDir = Join-Path "dist" $releaseName
New-Item -ItemType Directory -Path (Join-Path $releaseDir "docs") -Force | Out-Null
Copy-Item "dist\Commercial1688DraftTool.exe" $releaseDir -Force
Copy-Item "README.md" $releaseDir -Force
Copy-Item "VERSION" $releaseDir -Force
Copy-Item "CHANGELOG.md" $releaseDir -Force
Copy-Item "docs\*" (Join-Path $releaseDir "docs") -Recurse -Force
$hash = (Get-FileHash (Join-Path $releaseDir "Commercial1688DraftTool.exe") -Algorithm SHA256).Hash
Set-Content -LiteralPath (Join-Path $releaseDir "SHA256SUMS.txt") -Value "$hash  Commercial1688DraftTool.exe" -Encoding ascii
Compress-Archive -Path "$releaseDir\*" -DestinationPath "dist\$releaseName.zip" -CompressionLevel Optimal -Force
Write-Host "Build completed: dist\$releaseName.zip"
