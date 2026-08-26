[CmdletBinding()]
param(
    [string]$PythonExe = "",
    [string]$InnoSetupExe = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$BuildRoot = Join-Path $ProjectRoot "build"
$VenvRoot = Join-Path $BuildRoot ".venv"
$PyInstallerWork = Join-Path $BuildRoot "w"
$PyInstallerDist = Join-Path $BuildRoot "p"
$InstallerOutputDir = Join-Path $ProjectRoot "dist"
$Requirements = Join-Path $ProjectRoot "requirements.txt"
$EntryPoint = Join-Path $ProjectRoot "app\main.py"
$InstallerScript = Join-Path $ProjectRoot "installer\PII-Log-Cleaner.iss"
$ProjectLicense = Join-Path $ProjectRoot "LICENSE"
$ProjectNotice = Join-Path $ProjectRoot "NOTICE"
$ThirdPartyNotices = Join-Path $ProjectRoot "THIRD_PARTY_NOTICES.md"
$AppIcon = Join-Path $ProjectRoot "resources\icons\branding\pii-log-cleaner-icon.ico"
$BundledModelPath = Join-Path $ProjectRoot "models\schift-ko-pii-v6"

function Test-PythonRuntime {
    param(
        [string]$Command,
        [string[]]$Prefix = @()
    )
    & $Command @Prefix -c "import sys; assert sys.version_info >= (3, 10) and sys.maxsize > 2**32" 1>$null 2>$null
    return $LASTEXITCODE -eq 0
}

function Get-PythonApplications {
    param([string[]]$Names)
    $paths = foreach ($name in $Names) {
        Get-Command -Name $name -CommandType Application -All -ErrorAction SilentlyContinue |
            ForEach-Object {
                if ($_.Path) { $_.Path } elseif ($_.Source) { $_.Source }
            }
    }
    return @($paths | Where-Object { $_ } | Select-Object -Unique)
}

function Resolve-Python {
    if ($PythonExe) {
        $candidate = if (Test-Path -LiteralPath $PythonExe -PathType Leaf) {
            (Resolve-Path -LiteralPath $PythonExe).Path
        } else {
            @(Get-PythonApplications @($PythonExe) | Select-Object -First 1)
        }
        if (-not $candidate) {
            throw "지정한 Python 실행 파일을 찾지 못했습니다: $PythonExe"
        }
        $script:PythonArguments = @()
        if (-not (Test-PythonRuntime -Command $candidate)) {
            throw "지정한 Python은 64-bit Python 3.10 이상이 아닙니다: $candidate"
        }
        return $candidate
    }
    foreach ($launcher in (Get-PythonApplications @("py.exe", "py"))) {
        if (Test-PythonRuntime -Command $launcher -Prefix @("-3")) {
            $script:PythonArguments = @("-3")
            return $launcher
        }
    }
    foreach ($python in (Get-PythonApplications @("python.exe", "python", "python3.exe", "python3"))) {
        if (Test-PythonRuntime -Command $python) {
            $script:PythonArguments = @()
            return $python
        }
    }
    throw "64-bit Python 3.10 이상을 찾지 못했습니다. 'python -V'를 확인하거나 -PythonExe로 python.exe 경로를 지정해주세요."
}

function Invoke-Python {
    param([string[]]$Arguments)
    & $script:PythonCommand @script:PythonArguments @Arguments
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

function Restore-ModelWeights {
    param([string]$Snapshot)
    $weights = Join-Path $Snapshot "model.safetensors"
    if (Test-Path -LiteralPath $weights -PathType Leaf) { return }

    $parts = @(Get-ChildItem -LiteralPath $Snapshot -File -Filter "model.safetensors.part-*" -ErrorAction SilentlyContinue | Sort-Object Name)
    if ($parts.Count -eq 0) {
        throw "번들 모델 가중치 조각을 찾지 못했습니다: $Snapshot"
    }
    $checksumPath = Join-Path $Snapshot "model.safetensors.sha256"
    if (-not (Test-Path -LiteralPath $checksumPath -PathType Leaf)) {
        throw "번들 모델 SHA-256 파일을 찾지 못했습니다: $checksumPath"
    }
    $expected = ((Get-Content -LiteralPath $checksumPath -Raw).Trim() -split "\s+")[0].ToLowerInvariant()
    if ($expected -notmatch "^[a-f0-9]{64}$") {
        throw "번들 모델 SHA-256 형식이 올바르지 않습니다: $checksumPath"
    }

    $partial = "$weights.$PID.partial"
    $target = [System.IO.File]::Open($partial, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write)
    try {
        foreach ($part in $parts) {
            $source = [System.IO.File]::OpenRead($part.FullName)
            try { $source.CopyTo($target) } finally { $source.Dispose() }
        }
    } finally {
        $target.Dispose()
    }
    $actual = (Get-FileHash -LiteralPath $partial -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected) {
        throw "번들 모델 SHA-256 검증에 실패했습니다. 저장소를 다시 받아주세요."
    }
    Move-Item -LiteralPath $partial -Destination $weights
}

function Assert-ModelSnapshot {
    param([string]$Snapshot)
    if (-not (Test-Path -LiteralPath $Snapshot -PathType Container)) {
        throw "모델 스냅샷 폴더가 없습니다: $Snapshot`n모델 가중치는 저장소에 포함되지 않습니다. schift-ko-pii-v6을 내려받아 추출한 실제 폴더를 -ModelPath로 지정해주세요."
    }
    $required = @("config.json", "tokenizer.json", "tokenizer_config.json", "model.safetensors", "modeling_lfm2_bidirectional.py")
    $missing = $required | Where-Object { -not (Test-Path -LiteralPath (Join-Path $Snapshot $_) -PathType Leaf) }
    if ($missing) {
        throw "모델 스냅샷에 필수 파일이 없습니다: $($missing -join ', ')"
    }
    if (-not (Get-ChildItem -LiteralPath $Snapshot -File -Filter "LICENSE*" | Select-Object -First 1)) {
        throw "모델 라이선스 파일(LICENSE*)이 없습니다. 라이선스를 포함한 스냅샷을 사용해주세요."
    }
}

if ($env:OS -ne "Windows_NT") { throw "이 스크립트는 Windows에서만 실행할 수 있습니다." }
$ModelSnapshot = $BundledModelPath
Restore-ModelWeights $ModelSnapshot
Assert-ModelSnapshot $ModelSnapshot
$ModelSnapshot = (Resolve-Path -LiteralPath $ModelSnapshot).Path
$script:PythonArguments = @()
$script:PythonCommand = Resolve-Python

$missingLegalFiles = @($ProjectLicense, $ProjectNotice, $ThirdPartyNotices) | Where-Object { -not (Test-Path $_ -PathType Leaf) }
if ($missingLegalFiles) {
    throw "배포 고지 파일이 없습니다: $($missingLegalFiles -join ', ')"
}
if (-not (Test-Path $AppIcon -PathType Leaf)) { throw "앱 아이콘 파일을 찾지 못했습니다: $AppIcon" }
New-Item -ItemType Directory -Force -Path $BuildRoot, $PyInstallerWork, $PyInstallerDist, $InstallerOutputDir | Out-Null

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
& $VenvPython -m PyInstaller `
    --noconfirm --clean --windowed `
    --name "PII" `
    --icon $AppIcon `
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

$AppExe = Join-Path $PyInstallerDist "PII\PII.exe"
if (-not (Test-Path $AppExe -PathType Leaf)) { throw "빌드된 실행 파일을 찾지 못했습니다: $AppExe" }

$Iscc = Resolve-Iscc
& $Iscc "--output-dir=$InstallerOutputDir" $InstallerScript
if ($LASTEXITCODE -ne 0) { throw "Inno Setup 빌드에 실패했습니다." }

$Installer = Join-Path $InstallerOutputDir "PII-Log-Cleaner-Setup.exe"
if (-not (Test-Path $Installer -PathType Leaf)) { throw "설치 파일을 찾지 못했습니다: $Installer" }
Write-Host "완료: $Installer"
