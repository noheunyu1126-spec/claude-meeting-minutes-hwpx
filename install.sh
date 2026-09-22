#!/usr/bin/env bash
# 회의록 작성 스킬 설치 (macOS / Linux)
#
#   bash install.sh
#
# ~/.claude/ 아래에 스킬과 /회의록 커맨드를 놓는다.
# 참고: HWPX 생성 자체는 되지만, 결과 확인·PDF 변환은 한컴오피스 한글(Windows)이
#       필요하다. 이 환경에서는 --pdf 옵션이 동작하지 않는다.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$HOME/.claude"
SKILL="$ROOT/skills/meeting-minutes-hwpx"
CMDS="$ROOT/commands"

echo
echo "  회의록 작성 스킬 설치"
echo "  대상: $ROOT"
echo

confirm_overwrite() {   # $1=path  $2=label
  [ -e "$1" ] || return 0
  echo "  이미 있습니다: $2"
  read -r -p "  덮어쓸까요? (y/N) " a
  [ "$a" = "y" ] || [ "$a" = "Y" ]
}

# --- 스킬 -------------------------------------------------------------
if confirm_overwrite "$SKILL" "skills/meeting-minutes-hwpx"; then
  mkdir -p "$SKILL"
  cp -R "$SRC/skills/meeting-minutes-hwpx/." "$SKILL/"
  echo "  [완료] 스킬 복사"
else
  echo "  [건너뜀] 스킬"
fi

# --- 커맨드 -----------------------------------------------------------
if confirm_overwrite "$CMDS/회의록.md" "commands/회의록.md"; then
  mkdir -p "$CMDS"
  cp "$SRC/commands/회의록.md" "$CMDS/회의록.md"
  echo "  [완료] /회의록 커맨드 등록"
else
  echo "  [건너뜀] 커맨드"
fi

# --- defaults.json ----------------------------------------------------
if [ ! -f "$SKILL/defaults.json" ]; then
  cp "$SKILL/defaults.example.json" "$SKILL/defaults.json"
  echo "  [완료] defaults.json 생성 — 작성자·관리자·장소를 고쳐 주세요"
else
  echo "  [유지] defaults.json (기존 설정 보존)"
fi

# --- 파이썬 패키지 ----------------------------------------------------
echo
echo "  파이썬 패키지 확인..."
if command -v python3 >/dev/null 2>&1; then
  python3 -m pip install --quiet --disable-pip-version-check lxml pymupdf \
    && echo "  [완료] lxml, pymupdf  (pywin32 는 Windows 전용이라 건너뜀)" \
    || echo "  [경고] 설치 실패 — 수동으로: pip install lxml pymupdf"
else
  echo "  [경고] python3 을 찾을 수 없습니다."
fi

# --- 빌드 검증 --------------------------------------------------------
echo
echo "  빌드 검증..."
( cd "$SKILL" && python3 scripts/build_minutes.py --selftest \
    -o "${TMPDIR:-/tmp}/회의록_설치확인.hwpx" | grep '"PASS"' ) || true
rm -f "${TMPDIR:-/tmp}/회의록_설치확인.hwpx"

echo
echo "  설치 완료. Claude Code 를 다시 시작한 뒤 /회의록 을 입력해 보세요."
echo
