# 회의록 작성 스킬 설치 (Windows)
#
#   powershell -ExecutionPolicy Bypass -File install.ps1
#
# ~/.claude/ 아래에 스킬과 /회의록 커맨드를 놓고, 파이썬 패키지를 확인한다.
# 이미 있는 파일은 덮어쓰기 전에 물어본다.

$ErrorActionPreference = "Stop"
$src   = Split-Path -Parent $MyInvocation.MyCommand.Path
$root  = Join-Path $env:USERPROFILE ".claude"
$skill = Join-Path $root "skills\meeting-minutes-hwpx"
$cmds  = Join-Path $root "commands"

Write-Host ""
Write-Host "  회의록 작성 스킬 설치" -ForegroundColor Cyan
Write-Host "  대상: $root"
Write-Host ""

function Confirm-Overwrite($path, $label) {
    if (-not (Test-Path $path)) { return $true }
    Write-Host "  이미 있습니다: $label" -ForegroundColor Yellow
    $a = Read-Host "  덮어쓸까요? (y/N)"
    return ($a -eq "y" -or $a -eq "Y")
}

# --- 스킬 -------------------------------------------------------------
if (Confirm-Overwrite $skill "skills\meeting-minutes-hwpx") {
    New-Item -ItemType Directory -Force -Path $skill | Out-Null
    Copy-Item (Join-Path $src "skills\meeting-minutes-hwpx\*") $skill -Recurse -Force
    Write-Host "  [완료] 스킬 복사" -ForegroundColor Green
} else {
    Write-Host "  [건너뜀] 스킬"
}

# --- 커맨드 -----------------------------------------------------------
$cmdFile = Join-Path $cmds "회의록.md"
if (Confirm-Overwrite $cmdFile "commands\회의록.md") {
    New-Item -ItemType Directory -Force -Path $cmds | Out-Null
    Copy-Item (Join-Path $src "commands\회의록.md") $cmdFile -Force
    Write-Host "  [완료] /회의록 커맨드 등록" -ForegroundColor Green
} else {
    Write-Host "  [건너뜀] 커맨드"
}

# --- defaults.json ----------------------------------------------------
$dj = Join-Path $skill "defaults.json"
if (-not (Test-Path $dj)) {
    Copy-Item (Join-Path $skill "defaults.example.json") $dj -Force
    Write-Host "  [완료] defaults.json 생성 — 작성자·관리자·장소를 고쳐 주세요" -ForegroundColor Green
} else {
    Write-Host "  [유지] defaults.json (기존 설정 보존)"
}

# --- 파이썬 패키지 ----------------------------------------------------
Write-Host ""
Write-Host "  파이썬 패키지 확인..."
$py = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $py) {
    Write-Host "  [경고] python 을 찾을 수 없습니다. python.org 에서 설치하세요." -ForegroundColor Yellow
} else {
    & python -m pip install --quiet --disable-pip-version-check lxml pymupdf pywin32
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [완료] lxml, pymupdf, pywin32" -ForegroundColor Green
    } else {
        Write-Host "  [경고] 패키지 설치 실패 — 수동으로: pip install lxml pymupdf pywin32" -ForegroundColor Yellow
    }
}

# --- 빌드 검증 --------------------------------------------------------
Write-Host ""
Write-Host "  빌드 검증..."
$tmp = Join-Path $env:TEMP "회의록_설치확인.hwpx"
Push-Location $skill
& python "scripts\build_minutes.py" --selftest -o $tmp 2>&1 | Select-String '"PASS"'
Pop-Location
Remove-Item $tmp -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "  설치 완료." -ForegroundColor Cyan
Write-Host "  Claude Code 를 다시 시작한 뒤 /회의록 을 입력해 보세요."
Write-Host ""
