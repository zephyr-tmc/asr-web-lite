$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

function Require-File {
    param(
        [string]$Path,
        [string]$Message
    )
    if (-not (Test-Path $Path)) {
        throw $Message
    }
}

function Find-Python {
    $Candidates = @(
        [pscustomobject]@{ Exe = "py"; Args = @("-3.12") },
        [pscustomobject]@{ Exe = "py"; Args = @("-3.11") },
        [pscustomobject]@{ Exe = "py"; Args = @("-3.10") },
        [pscustomobject]@{ Exe = "python"; Args = @() }
    )
    foreach ($Candidate in $Candidates) {
        try {
            & $Candidate.Exe @($Candidate.Args + @("-c", "import sys; raise SystemExit(0 if (3, 10) <= sys.version_info < (3, 13) else 1)")) *> $null
            if ($LASTEXITCODE -eq 0) {
                return $Candidate
            }
        }
        catch {
        }
    }
    return $null
}

function Invoke-BuildPython {
    param([string[]]$Arguments)
    & $script:PythonCommand.Exe @($script:PythonCommand.Args + $Arguments)
}

Write-Host "ASR Web Lite Windows 打包脚本"
Write-Host ""

Require-File "bin\ffmpeg.exe" "缺少 bin\ffmpeg.exe。请放入 Windows 版 ffmpeg。"
Require-File "bin\ffprobe.exe" "缺少 bin\ffprobe.exe。请放入 Windows 版 ffprobe。"
Require-File "models\medium.pt" "缺少 models\medium.pt。为保证新机器离线可用，Windows 安装包默认要求内置 medium 模型。"

$script:PythonCommand = Find-Python
if (-not $script:PythonCommand) {
    throw "打包机需要 Python 3.10-3.12。"
}

Invoke-BuildPython @("scripts\bootstrap.py")
if ($LASTEXITCODE -ne 0) {
    throw "依赖安装失败。"
}

.\.venv\Scripts\python.exe -m pip install pyinstaller
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 安装失败。"
}

.\.venv\Scripts\pyinstaller.exe --noconfirm --clean "ASR Web Lite Windows.spec"
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 打包失败。"
}

Write-Host ""
Write-Host "便携版已生成：dist\ASR Web Lite\ASR Web Lite.exe"

$Iscc = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
if ($Iscc) {
    & $Iscc.Source "installer\windows\ASRWebLite.iss"
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup 安装包生成失败。"
    }
    Write-Host "安装包已生成：dist\installer\ASR-Web-Lite-Setup.exe"
}
else {
    Write-Host "未检测到 Inno Setup，已跳过 .exe 安装包生成。"
    Write-Host "如需安装包，请安装 Inno Setup 6 后重新运行本脚本。"
}
