param([switch]$OverwriteLocalBuild)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path ".venv\Scripts\python.exe")) { & "$PSScriptRoot\install.ps1" }
$pythonPath = ".venv\Scripts\python.exe"
& $pythonPath scripts/check_version.py
if ($LASTEXITCODE -ne 0) { throw "Version consistency check failed (exit code $LASTEXITCODE)." }
$version = (Get-Content VERSION -Raw).Trim()
$releaseName = "Commercial1688DraftTool-$version-win64"
$releaseDir = Join-Path "dist" $releaseName
$archivePath = Join-Path "dist" "$releaseName.zip"
$archiveHashPath = "$archivePath.sha256"
$existingOutputs = @($releaseDir, $archivePath, $archiveHashPath) | Where-Object { Test-Path -LiteralPath $_ }
if ($existingOutputs -and -not $OverwriteLocalBuild) { throw "Release output already exists: $($existingOutputs -join ', '). Increment VERSION or pass -OverwriteLocalBuild for an intentional local rebuild." }
if ($OverwriteLocalBuild) { foreach ($path in $existingOutputs) { Remove-Item -LiteralPath $path -Recurse -Force } }
& $pythonPath -c "import PyInstaller"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller is unavailable. Install requirements-build.txt first." }
# PyInstaller otherwise silently excludes tkinter when Tcl cannot initialize.
& $pythonPath -c "import tkinter; tkinter.Tcl()"
if ($LASTEXITCODE -ne 0) { throw "Tcl initialization failed; cannot build the launcher." }
$pyInstallerDist = Join-Path "build" "pyinstaller-dist"
$pyInstallerWork = Join-Path "build" "pyinstaller-work"
$pyInstallerSpec = Join-Path "build" "pyinstaller-spec"
New-Item -ItemType Directory -Path $pyInstallerDist, $pyInstallerWork, $pyInstallerSpec -Force | Out-Null
& $pythonPath -m PyInstaller --noconfirm --clean --name Commercial1688DraftTool --onefile --windowed --paths src --distpath $pyInstallerDist --workpath $pyInstallerWork --specpath $pyInstallerSpec --collect-submodules draft_tool --collect-all DrissionPage --collect-all bs4 --collect-all PIL --add-data "README.md;." --add-data "docs/操作说明.md;docs" --add-data "docs/环境配置.md;docs" --add-data "docs/compatibility.md;docs" "src\draft_tool\launcher.py"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed (exit code $LASTEXITCODE)." }
New-Item -ItemType Directory -Path (Join-Path $releaseDir "docs") -Force | Out-Null
Copy-Item (Join-Path $pyInstallerDist "Commercial1688DraftTool.exe") $releaseDir
Copy-Item "README.md", "VERSION", "CHANGELOG.md" $releaseDir
$releaseDocs = @("docs/操作说明.md", "docs/环境配置.md", "docs/compatibility.md", "docs/版本说明-$version.md")
foreach ($document in $releaseDocs) { if (-not (Test-Path -LiteralPath $document)) { throw "Required release document is missing: $document" }; Copy-Item -LiteralPath $document -Destination (Join-Path $releaseDir "docs") }
$exePath = Join-Path $releaseDir "Commercial1688DraftTool.exe"
$exeHash = (Get-FileHash $exePath -Algorithm SHA256).Hash
Set-Content -LiteralPath (Join-Path $releaseDir "SHA256SUMS.txt") -Value "$exeHash  Commercial1688DraftTool.exe" -Encoding ascii
Compress-Archive -Path "$releaseDir\*" -DestinationPath $archivePath -CompressionLevel Optimal
$verificationOutput = Join-Path ".local" "package-verification-$version.json"
& $pythonPath scripts/verify_release.py --archive $archivePath --expected-version $version --output $verificationOutput
if ($LASTEXITCODE -ne 0) { throw "Release verification failed (exit code $LASTEXITCODE)." }
$archiveHash = (Get-FileHash $archivePath -Algorithm SHA256).Hash
Set-Content -LiteralPath $archiveHashPath -Value "$archiveHash  $releaseName.zip" -Encoding ascii
Write-Host "Build and verification completed: $archivePath"
