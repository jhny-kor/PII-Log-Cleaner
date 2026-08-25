[CmdletBinding()]
param(
    [string]$ModelPath = (Join-Path $PSScriptRoot "models\schift-ko-pii-v6"),
    [string]$PythonExe = "",
    [string]$InnoSetupExe = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$BuildRoot = Join-Path $ProjectRoot "build"
$VenvRoot = Join-Path $BuildRoot ".venv"
$PyInstallerWork = Join-Path $BuildRoot "pyinstaller-work"
$PyInstallerDist = Join-Path $BuildRoot "pyinstaller"
$Requirements = Join-Path $ProjectRoot "requirements.txt"
$EntryPoint = Join-Path $ProjectRoot "app\main.py"
$InstallerScript = Join-Path $ProjectRoot "installer\PII-Log-Cleaner.iss"
$ProjectLicense = Join-Path $ProjectRoot "LICENSE"
$ProjectNotice = Join-Path $ProjectRoot "NOTICE"
$ThirdPartyNotices = Join-Path $ProjectRoot "THIRD_PARTY_NOTICES.md"

function Resolve-Python {
    if ($PythonExe) {
        return $PythonExe
    }
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        return "py.exe"
    }
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }
    throw "Python 3.10 이상(64-bit)을 찾지 못했습니다. -PythonExe로 지정해주세요."
}

function Invoke-Python {
    param([string[]]$Arguments)
    if ($script:PythonCommand -eq "py.exe") {
        & $script:PythonCommand "-3.11" @Arguments
    } else {
        & $script:PythonCommand @Arguments
    }
    if ($LASTEXITCODE -ne 0) { throw "Python 명령이 실패했습니다: $Arguments" }
}

function Resolve-Iscc {
    if ($InnoSetupExe) { return $InnoSetupExe }
    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    foreach ($candidate in @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )) {
        if ($candidate -and (Test-Path $candidate)) { return $candidate }
    }
    throw "Inno Setup 6의 ISCC.exe를 찾지 못했습니다. 설치하거나 -InnoSetupExe로 경로를 지정해주세요."
}

function Assert-ModelSnapshot {
    param([string]$Snapshot)
    if (-not (Test-Path $Snapshot -PathType Container)) {
        throw "모델 스냅샷 폴더가 없습니다: $Snapshot"
    }
    $required = @("config.json", "tokenizer.json", "tokenizer_config.json", "model.safetensors", "modeling_lfm2_bidirectional.py")
    $missing = $required | Where-Object { -not (Test-Path (Join-Path $Snapshot $_) -PathType Leaf) }
    if ($missing) {
        throw "모델 스냅샷에 필수 파일이 없습니다: $($missing -join ', ')"
    }
    if (-not (Get-ChildItem $Snapshot -File -Filter "LICENSE*" | Select-Object -First 1)) {
        throw "모델 라이선스 파일(LICENSE*)이 없습니다. 라이선스를 포함한 스냅샷을 사용해주세요."
    }
}

if ($env:OS -ne "Windows_NT") { throw "이 스크립트는 Windows에서만 실행할 수 있습니다." }
$script:PythonCommand = Resolve-Python
if ($script:PythonCommand -eq "py.exe") {
    & $script:PythonCommand -3.11 -c "import platform, sys; assert sys.version_info >= (3, 10) and platform.architecture()[0] == '64bit'"
} else {
    & $script:PythonCommand -c "import platform, sys; assert sys.version_info >= (3, 10) and platform.architecture()[0] == '64bit'"
}
if ($LASTEXITCODE -ne 0) { throw "64-bit Python 3.10 이상이 필요합니다." }

Assert-ModelSnapshot (Resolve-Path $ModelPath)
$missingLegalFiles = @($ProjectLicense, $ProjectNotice, $ThirdPartyNotices) | Where-Object { -not (Test-Path $_ -PathType Leaf) }
if ($missingLegalFiles) {
    throw "배포 고지 파일이 없습니다: $($missingLegalFiles -join ', ')"
}
New-Item -ItemType Directory -Force -Path $BuildRoot, $PyInstallerWork, $PyInstallerDist | Out-Null

if (-not (Test-Path (Join-Path $VenvRoot "Scripts\python.exe"))) {
    Invoke-Python @("-m", "venv", $VenvRoot)
}
$VenvPython = Join-Path $VenvRoot "Scripts\python.exe"
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip 업그레이드에 실패했습니다." }

# The released installer is CPU-only; no GPU runtime is pulled into the bundle.
& $VenvPython -m pip install --index-url https://download.pytorch.org/whl/cpu torch
if ($LASTEXITCODE -ne 0) { throw "CPU 전용 PyTorch 설치에 실패했습니다." }
& $VenvPython -m pip install -r $Requirements
if ($LASTEXITCODE -ne 0) { throw "패키지 설치에 실패했습니다." }

$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$ModelSnapshot = (Resolve-Path $ModelPath).Path
& $VenvPython -m PyInstaller `
    --noconfirm --clean --windowed `
    --name "PII Log Cleaner" `
    --paths $ProjectRoot `
    --workpath $PyInstallerWork `
    --distpath $PyInstallerDist `
    --specpath $BuildRoot `
    --add-data "$ModelSnapshot;models\schift-ko-pii-v6" `
    --add-data "$(Join-Path $ProjectRoot 'resources');resources" `
    --add-data "$ProjectLicense;." `
    --add-data "$ProjectNotice;." `
    --add-data "$ThirdPartyNotices;." `
    --collect-all PySide6 `
    --collect-all schift_ko_pii `
    --hidden-import transformers.models.lfm2 `
    --hidden-import transformers.models.lfm2.configuration_lfm2 `
    --hidden-import transformers.models.lfm2.modeling_lfm2 `
    --hidden-import safetensors.torch `
    $EntryPoint
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 빌드에 실패했습니다." }

$AppExe = Join-Path $PyInstallerDist "PII Log Cleaner\PII Log Cleaner.exe"
if (-not (Test-Path $AppExe -PathType Leaf)) { throw "빌드된 실행 파일을 찾지 못했습니다: $AppExe" }

$Iscc = Resolve-Iscc
& $Iscc $InstallerScript
if ($LASTEXITCODE -ne 0) { throw "Inno Setup 빌드에 실패했습니다." }

$Installer = Join-Path $ProjectRoot "dist\PII-Log-Cleaner-Setup.exe"
if (-not (Test-Path $Installer -PathType Leaf)) { throw "설치 파일을 찾지 못했습니다: $Installer" }
Write-Host "완료: $Installer"
