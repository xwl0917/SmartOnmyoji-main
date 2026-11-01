#Requires -Version 5.1
<#
.SYNOPSIS
    Build SmartOnmyoji into a Windows onedir executable with PyInstaller.

.DESCRIPTION
    The script:
      1. checks the project layout and locates a Python 3.9-3.13 interpreter;
      2. creates/uses an isolated virtual environment (default: .venv-build);
      3. installs requirements.txt and PyInstaller;
      4. runs PyInstaller with smart_onmyoji_start.spec;
      5. verifies the packaged assets, removes __pycache__ and local click logs;
      6. optionally creates Release\SmartOnmyoji-<version>-win64.zip.

    Output:
      Release\smart_onmyoji_start\smart_onmyoji_start.exe

.PARAMETER Python
    Base interpreter used to create the build venv, e.g. "py" or
    "C:\Python312\python.exe". When omitted the script tries py -3.13 ... -3.9
    and then "python". Ignored when the venv already exists.

.PARAMETER VenvDir
    Build virtual environment directory, relative to the project root.

.PARAMETER OutDir
    PyInstaller dist directory, relative to the project root.

.PARAMETER IndexUrl
    Optional pip index URL, e.g. https://pypi.tuna.tsinghua.edu.cn/simple.

.PARAMETER SkipInstall
    Do not run pip. The venv must already contain PyInstaller and all runtime
    dependencies. Useful for offline rebuilds.

.PARAMETER RecreateVenv
    Delete and recreate the build venv before installing.

.PARAMETER NoZip
    Do not create the release zip.

.PARAMETER StrictTemplates
    Fail the build when validate_templates.py reports errors. By default the
    validator only warns, so an existing broken custom template folder does not
    block packaging.

.PARAMETER SkipSelfCheck
    Do not run the packaged exe with --self-check after building. Use this on
    headless build machines; the check creates a QApplication to verify the Qt
    platform/image plugins.

.PARAMETER DryRun
    Only print the detected environment and planned paths, then exit.

.EXAMPLE
    .\build_exe.ps1

.EXAMPLE
    .\build_exe.ps1 -IndexUrl https://pypi.tuna.tsinghua.edu.cn/simple

.EXAMPLE
    .\build_exe.ps1 -SkipInstall -NoZip
#>
[CmdletBinding()]
param(
    [string]$Python = "",
    [string]$VenvDir = ".venv-build",
    [string]$OutDir = "Release",
    [string]$IndexUrl = "",
    [switch]$SkipInstall,
    [switch]$RecreateVenv,
    [switch]$NoZip,
    [switch]$StrictTemplates,
    [switch]$SkipSelfCheck,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$script:Root = $PSScriptRoot
if (-not $script:Root) {
    $script:Root = Split-Path -Parent $MyInvocation.MyCommand.Path
}
$script:Root = (Resolve-Path -LiteralPath $script:Root).Path
Set-Location -LiteralPath $script:Root

$script:StepNo = 0
$script:AppName = "smart_onmyoji_start"

function Write-Step {
    param([string]$Message)
    $script:StepNo = $script:StepNo + 1
    Write-Host ""
    Write-Host ("== Step {0}: {1}" -f $script:StepNo, $Message) -ForegroundColor Cyan
}

function Fail {
    param([string]$Message)
    Write-Host ""
    Write-Host ("[ERROR] " + $Message) -ForegroundColor Red
    exit 1
}

function Remove-ProjectPath {
    param([string]$Path)
    $full = (Resolve-Path -LiteralPath $Path).Path
    if (-not $full.StartsWith($script:Root, [System.StringComparison]::OrdinalIgnoreCase)) {
        Fail "Refusing to delete a path outside the project: $full"
    }
    Write-Host ("  removing " + $full)
    Remove-Item -LiteralPath $full -Recurse -Force
}

function Get-PythonVersion {
    param(
        [string]$Exe,
        [string[]]$PreArgs = @()
    )
    try {
        $output = & $Exe @PreArgs --version 2>&1
        if ($LASTEXITCODE -ne 0) {
            return $null
        }
        $text = ($output | Out-String)
        if ($text -match 'Python (\d+)\.(\d+)') {
            return [version]("{0}.{1}" -f $Matches[1], $Matches[2])
        }
    } catch {
        return $null
    }
    return $null
}

function Test-SupportedPython {
    param([version]$Version)
    return ($Version -ge [version]"3.9" -and $Version -lt [version]"3.14")
}

function Test-IsWindows64 {
    if ($env:OS -ne "Windows_NT") {
        return $false
    }
    return [Environment]::Is64BitOperatingSystem
}

# ---------------------------------------------------------------------------
# 1. Basic environment checks
# ---------------------------------------------------------------------------
Write-Step "Checking environment and project files"

if (-not (Test-IsWindows64)) {
    Fail "This script requires 64-bit Windows."
}

if ([System.IO.Path]::IsPathRooted($VenvDir) -or [System.IO.Path]::IsPathRooted($OutDir)) {
    Fail "VenvDir and OutDir must be relative to the project root."
}

$requiredFiles = @(
    "smart_onmyoji_start.py",
    "smart_onmyoji_start.spec",
    "requirements.txt",
    "logo.ico",
    "img",
    "modules\config.ini",
    "modules\adb.exe",
    "modules\tools\manual.html"
)
foreach ($relative in $requiredFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $script:Root $relative))) {
        Fail ("Missing required file or folder: " + $relative)
    }
}

Write-Host ("  project root : " + $script:Root)
Write-Host "  source files : OK"

$configPath = Join-Path $script:Root "modules\config.ini"
$configText = Get-Content -LiteralPath $configPath -Raw
if ($configText -match '(?m)^\s*handle_num\s*=\s*[1-9]') {
    Write-Warning "modules/config.ini contains a saved handle_num. It will be shipped as-is."
}
if ($configText -match '(?m)^\s*temporary_custom_target_path\s*=\s*[A-Za-z]:[\\/]') {
    Write-Warning "modules/config.ini contains a machine-specific absolute path. It will be shipped as-is."
}

# ---------------------------------------------------------------------------
# 2. Locate a supported interpreter / venv
# ---------------------------------------------------------------------------
Write-Step "Locating Python 3.9-3.13"

$venvDirPath = Join-Path $script:Root $VenvDir
$venvPython = Join-Path $venvDirPath "Scripts\python.exe"
$baseExe = $null
$baseArgs = @()
$baseVersion = $null
$venvVersion = $null

if ($RecreateVenv -and (Test-Path -LiteralPath $venvDirPath)) {
    Remove-ProjectPath $venvDirPath
}

if (Test-Path -LiteralPath $venvPython) {
    $venvVersion = Get-PythonVersion $venvPython
    if (-not $venvVersion) {
        Fail ("Existing venv is broken: " + $venvPython + ". Delete it or use -RecreateVenv.")
    }
    if (-not (Test-SupportedPython $venvVersion)) {
        Fail ("Existing venv uses Python " + $venvVersion + "; 3.9-3.13 is required. Use -RecreateVenv -Python <exe>.")
    }
    Write-Host ("  venv         : " + $venvPython + " (Python " + $venvVersion + ")")
} else {
    if ($Python) {
        $baseExe = $Python
        $baseVersion = Get-PythonVersion $baseExe
        if (-not $baseVersion) {
            Fail ("Cannot run the interpreter given by -Python: " + $Python)
        }
        if (-not (Test-SupportedPython $baseVersion)) {
            Fail ("Python " + $baseVersion + " is not supported. Use 3.9-3.13.")
        }
    } else {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            foreach ($candidate in @("3.13", "3.12", "3.11", "3.10", "3.9")) {
                $version = Get-PythonVersion "py" @("-$candidate")
                if ($version -and (Test-SupportedPython $version)) {
                    $baseExe = "py"
                    $baseArgs = @("-$candidate")
                    $baseVersion = $version
                    break
                }
            }
        }
        if (-not $baseExe) {
            $version = Get-PythonVersion "python"
            if ($version -and (Test-SupportedPython $version)) {
                $baseExe = "python"
                $baseArgs = @()
                $baseVersion = $version
            }
        }
        if (-not $baseExe) {
            Fail "No Python 3.9-3.13 found. Install one from https://www.python.org/downloads/windows/ or pass -Python <python.exe>."
        }
    }

    $bits = [string]((& $baseExe @baseArgs -c "import struct; print(struct.calcsize('P') * 8)" | Select-Object -Last 1))
    if ($LASTEXITCODE -ne 0) {
        Fail "Failed to query the Python architecture."
    }
    if ($bits.Trim() -ne "64") {
        Fail ("A 64-bit Python is required, but " + $bits.Trim() + "-bit was found.")
    }

    Write-Host ("  base python  : " + $baseExe + " " + ($baseArgs -join " ") + " (Python " + $baseVersion + ")")
    Write-Host ("  venv to make : " + $venvDirPath)
}

$exePath = Join-Path (Join-Path (Join-Path $script:Root $OutDir) $script:AppName) ($script:AppName + ".exe")

if ($DryRun) {
    Write-Host ""
    Write-Host "Dry run summary:" -ForegroundColor Yellow
    if ($venvVersion) {
        Write-Host ("  interpreter : " + $venvPython + " (Python " + $venvVersion + ")")
    } else {
        Write-Host ("  interpreter : " + $venvPython + " (will be created with Python " + $baseVersion + ")")
    }
    Write-Host ("  output exe  : " + $exePath)
    Write-Host ("  install deps: " + (-not $SkipInstall))
    Write-Host ("  create zip  : " + (-not $NoZip))
    Write-Host ("  strict tmpl : " + $StrictTemplates)
    Write-Host ("  self-check  : " + (-not $SkipSelfCheck))
    exit 0
}

if (-not $venvVersion) {
    Write-Host "  creating venv ..."
    & $baseExe @baseArgs -m venv $venvDirPath
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $venvPython)) {
        # Do not leave a half-created venv behind (for example when ensurepip is blocked).
        if (Test-Path -LiteralPath $venvDirPath) {
            Remove-Item -LiteralPath $venvDirPath -Recurse -Force -ErrorAction SilentlyContinue
        }
        Fail ("Failed to create the virtual environment at " + $venvDirPath + ". Check that Python's venv/ensurepip works, or pass -VenvDir with an existing venv.")
    }
    $venvVersion = Get-PythonVersion $venvPython
    if (-not $venvVersion -or -not (Test-SupportedPython $venvVersion)) {
        Fail ("The new venv uses an unsupported Python: " + $venvVersion)
    }
    Write-Host ("  venv created : Python " + $venvVersion)
}

$venvBits = [string]((& $venvPython -c "import struct; print(struct.calcsize('P') * 8)" | Select-Object -Last 1))
if ($venvBits.Trim() -ne "64") {
    Fail ("The build venv is " + $venvBits.Trim() + "-bit; a 64-bit Python is required.")
}

& $venvPython -m pip --version | Out-Null
if ($LASTEXITCODE -ne 0) {
    Fail ("The venv at " + $venvDirPath + " has no working pip. Delete it (or use -RecreateVenv) and retry.")
}

# ---------------------------------------------------------------------------
# 3. Validate template data (stdlib only, runs before dependency install)
# ---------------------------------------------------------------------------
Write-Step "Validating template data"

$validatorPath = Join-Path $script:Root "modules\tools\validate_templates.py"
if (-not (Test-Path -LiteralPath $validatorPath)) {
    Fail ("Template validator not found: " + $validatorPath)
}
& $venvPython $validatorPath --root $script:Root
$validatorExit = $LASTEXITCODE
if ($validatorExit -ne 0) {
    if ($StrictTemplates) {
        Fail "Template validation failed. Fix the errors above, or omit -StrictTemplates."
    }
    Write-Warning "Template validation reported errors; continuing. Use -StrictTemplates to stop the build."
}

# ---------------------------------------------------------------------------
# 4. Install build dependencies
# ---------------------------------------------------------------------------
Write-Step "Installing build dependencies"

$pipArgs = @("-m", "pip", "install", "--disable-pip-version-check", "--no-input")
if ($IndexUrl) {
    $pipArgs += @("--index-url", $IndexUrl)
    Write-Host ("  index url    : " + $IndexUrl)
    if ($IndexUrl -match '^http://([^/]+)') {
        $trustedHost = $Matches[1]
        $pipArgs += @("--trusted-host", $trustedHost)
        Write-Host ("  trusted host : " + $trustedHost + " (HTTP index)")
    }
}

if ($SkipInstall) {
    Write-Host "  -SkipInstall: reusing packages already present in the venv."
    & $venvPython -c "import PyInstaller; print('  PyInstaller', PyInstaller.__version__)"
    if ($LASTEXITCODE -ne 0) {
        Fail ("PyInstaller is missing in " + $VenvDir + ". Run without -SkipInstall, or install it manually.")
    }
} else {
    Write-Host "  upgrading pip ..."
    & $venvPython @pipArgs --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        Fail "pip upgrade failed. Check the network or pass -IndexUrl."
    }

    Write-Host "  installing requirements.txt ..."
    & $venvPython @pipArgs -r (Join-Path $script:Root "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        Fail "pip install -r requirements.txt failed. Check the network or pass -IndexUrl."
    }

    Write-Host "  installing PyInstaller ..."
    & $venvPython @pipArgs "pyinstaller>=6.11"
    if ($LASTEXITCODE -ne 0) {
        Fail "PyInstaller installation failed."
    }
}

Write-Step "Verifying runtime imports"
$probe = "import cv2, PIL, PyQt5, pynput, pyautogui, numpy, win32gui, win32ui, win32com.client; print('  cv2', cv2.__version__); print('  numpy', numpy.__version__); print('  Pillow', PIL.__version__)"
& $venvPython -c $probe
if ($LASTEXITCODE -ne 0) {
    Fail "Runtime import check failed. See the error above."
}

# ---------------------------------------------------------------------------
# 5. Clean previous output
# ---------------------------------------------------------------------------
Write-Step "Cleaning previous build output"

$outRoot = Join-Path $script:Root $OutDir
$appDir = Join-Path $outRoot $script:AppName
$workAppDir = Join-Path (Join-Path $script:Root "build") $script:AppName

foreach ($path in @($appDir, $workAppDir)) {
    if (Test-Path -LiteralPath $path) {
        Remove-ProjectPath $path
    }
}
New-Item -ItemType Directory -Path $outRoot -Force | Out-Null

# ---------------------------------------------------------------------------
# 6. Run PyInstaller
# ---------------------------------------------------------------------------
Write-Step "Building with PyInstaller"

$specPath = Join-Path $script:Root "smart_onmyoji_start.spec"
$workRoot = Join-Path $script:Root "build"
$pyiArgs = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--log-level", "INFO",
    "--distpath", $outRoot,
    "--workpath", $workRoot,
    $specPath
)

Write-Host ("  " + $venvPython + " " + ($pyiArgs -join " "))
& $venvPython @pyiArgs
if ($LASTEXITCODE -ne 0) {
    Fail ("PyInstaller failed with exit code " + $LASTEXITCODE + ".")
}

# ---------------------------------------------------------------------------
# 7. Verify the bundled layout
# ---------------------------------------------------------------------------
Write-Step "Verifying packaged files"

if (-not (Test-Path -LiteralPath $exePath)) {
    Fail ("Executable not found: " + $exePath)
}

$dataRoot = $appDir
$internalDir = Join-Path $appDir "_internal"
if (Test-Path -LiteralPath $internalDir) {
    $dataRoot = $internalDir
}

$assets = @(
    @{ Path = (Join-Path $dataRoot "img"); Name = "img/" },
    @{ Path = (Join-Path $dataRoot "modules\config.ini"); Name = "modules/config.ini" },
    @{ Path = (Join-Path $dataRoot "modules\adb.exe"); Name = "modules/adb.exe" },
    @{ Path = (Join-Path $dataRoot "modules\tools\manual.html"); Name = "modules/tools/manual.html" },
    @{ Path = (Join-Path $dataRoot "modules\sounds\ding.wav"); Name = "modules/sounds/ding.wav" }
)
foreach ($asset in $assets) {
    if (-not (Test-Path -LiteralPath $asset.Path)) {
        Fail ("Missing packaged asset: " + $asset.Name)
    }
}
Write-Host ("  data root    : " + $dataRoot)
Write-Host "  assets       : OK"

# ---------------------------------------------------------------------------
# 8. Remove caches and local click logs from the package
# ---------------------------------------------------------------------------
Write-Step "Removing build caches and local click logs from the package"

$cacheDirs = @(Get-ChildItem -LiteralPath $dataRoot -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue)
foreach ($cacheDir in $cacheDirs) {
    if ($cacheDir.FullName.StartsWith($appDir, [System.StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $cacheDir.FullName -Recurse -Force
    }
}
Write-Host ("  __pycache__  : removed " + $cacheDirs.Count)

$clickLogDir = Join-Path $dataRoot "modules\click_log"
if (-not (Test-Path -LiteralPath $clickLogDir)) {
    New-Item -ItemType Directory -Path $clickLogDir -Force | Out-Null
}
$logFiles = @(Get-ChildItem -LiteralPath $clickLogDir -Filter "*.txt" -File -ErrorAction SilentlyContinue)
foreach ($logFile in $logFiles) {
    Remove-Item -LiteralPath $logFile.FullName -Force
}
Write-Host ("  click logs   : removed " + $logFiles.Count + " file(s), folder kept")

# ---------------------------------------------------------------------------
# 9. Run packaged self-check
# ---------------------------------------------------------------------------
if (-not $SkipSelfCheck) {
    Write-Step "Running packaged self-check"

    $selfCheckLog = Join-Path $appDir "selfcheck.log"
    if (Test-Path -LiteralPath $selfCheckLog) {
        Remove-Item -LiteralPath $selfCheckLog -Force
    }

    $process = Start-Process -FilePath $exePath -ArgumentList "--self-check" -PassThru -WindowStyle Hidden
    try {
        Wait-Process -Id $process.Id -Timeout 30 -ErrorAction Stop
    } catch {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        Fail "Packaged self-check timed out after 30 seconds. Check Qt plugins and selfcheck.log."
    }
    $process.Refresh()
    if ($process.ExitCode -ne 0) {
        Write-Host ("  self-check failed with exit code " + $process.ExitCode + ".") -ForegroundColor Red
        if (Test-Path -LiteralPath $selfCheckLog) {
            Get-Content -LiteralPath $selfCheckLog | ForEach-Object { Write-Host ("  " + $_) }
        }
        Fail "Packaged self-check failed. The trimmed Qt bundle or packaged assets may be incomplete."
    }

    if (Test-Path -LiteralPath $selfCheckLog) {
        $lastLine = Get-Content -LiteralPath $selfCheckLog | Select-Object -Last 1
        Write-Host ("  " + $lastLine)
        Remove-Item -LiteralPath $selfCheckLog -Force
    }
    Write-Host "  self-check   : OK"
} else {
    Write-Host ""
    Write-Host "-SkipSelfCheck: skipping packaged exe verification."
}

# ---------------------------------------------------------------------------
# 10. Optional release zip
# ---------------------------------------------------------------------------
$zipPath = $null
if (-not $NoZip) {
    Write-Step "Creating release zip"

    $tag = "v0.43"
    $entryText = Get-Content -LiteralPath (Join-Path $script:Root "smart_onmyoji_start.py") -Raw
    if ($entryText -match 'now_tag\s*=\s*"([^"]+)"') {
        $tag = $Matches[1]
    }

    $zipPath = Join-Path $outRoot ("SmartOnmyoji-" + $tag + "-win64.zip")
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    Compress-Archive -Path $appDir -DestinationPath $zipPath -CompressionLevel Optimal
    Write-Host ("  zip          : " + $zipPath)
}

# ---------------------------------------------------------------------------
# 11. Summary
# ---------------------------------------------------------------------------
$totalBytes = (Get-ChildItem -LiteralPath $appDir -Recurse -File | Measure-Object -Property Length -Sum).Sum
$sizeMB = [math]::Round($totalBytes / 1MB, 1)

Write-Host ""
Write-Host "Build completed successfully." -ForegroundColor Green
Write-Host ("  exe   : " + $exePath)
Write-Host ("  size  : " + $sizeMB + " MB")
if ($zipPath) {
    Write-Host ("  zip   : " + $zipPath)
}
Write-Host ""
Write-Host "Run the exe as administrator. The program also requests UAC elevation itself."
Write-Host "If the exe is flagged by antivirus, add an exclusion or rebuild with a code-signing certificate."
