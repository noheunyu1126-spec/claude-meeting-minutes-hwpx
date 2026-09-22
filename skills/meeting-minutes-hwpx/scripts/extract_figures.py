# -*- coding: utf-8 -*-
"""발표자료 PDF 에서 본문 텍스트와 '그림 후보'를 뽑아낸다.

    python extract_figures.py 자료.pdf -o ./_추출
    python extract_figures.py 자료.pdf -o ./_추출 --pages 3-20 --dpi 200

만들어지는 것
    _추출/text.md          쪽별 텍스트(내용 파악용). 쪽 제목과 그림 후보 목록이 함께 적힘
    _추출/figures.json     그림 후보 목록(쪽·위치·크기·주변 문구)
    _추출/fig_p05_1.png    그림 후보 이미지  ← 회의록에 넣을 때 이 파일을 쓴다
    _추출/pages/p05.png    쪽 전체 렌더(맥락 확인용, 낮은 해상도)

동작 방식
    쪽 안의 이미지·벡터 도형의 위치를 격자 마스크에 찍고, 붙어 있는 것끼리 묶어
    하나의 '그림 덩어리'로 본다. 로고·머리글·배경처럼 너무 작거나 너무 큰 덩어리는
    버리고, 남은 덩어리에 안쪽 글자와 바로 아래 캡션을 포함시켜 잘라낸다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import deque
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import fitz                                                   # PyMuPDF

CELL = 4.0          # 격자 한 칸 크기(pt)
DILATE = 2          # 덩어리 합치기용 팽창(칸) — 약 8pt 이내면 한 그림으로 본다
PAD = 3.0           # 잘라낼 때 여백(pt)

# 발표자료 폰트가 괄호·화살표 같은 기호를 CJK 호환/확장 문자로 심어 두는 일이 잦다.
# 그대로 두면 회의록 본문에 깨진 글자가 들어가므로 뜻이 분명한 것만 되돌리고,
# 애매한 글자는 손대지 않고 unknown_glyphs 로 보고해 사람이 판단하게 한다.
GLYPH_FIX = {
    "㏙": "(", "㏚": ")", "㏛": "[", "㏜": "]", "㏧": "「", "㏨": "」", "㛳": "→", "㝄": "→",
    "㐻": "→", "㏂": "→", "㍽": "→", "㚍": "→", "㚉": "+", "㚕": "~",
    "ㆍ": "·",  # 한글 아래아 — 가운됬점 자리에 쓰이는 경우
}
# CJK 호환·확장A·사용자정의 영역 — 여기 남아 있으면 깨진 글자일 가능성이 크다
_RARE = re.compile("[\u2e80-\u2fff\u3100-\u33ff\u3400-\u4dbf\ue000-\uf8ff]")
def normalize_text(t: str) -> str:
    if not t:
        return ""
    for a, b in GLYPH_FIX.items():
        t = t.replace(a, b)
    return t


# ------------------------------------------------------------------ 유틸 ----
def parse_pages(spec: str, n: int):
    if not spec:
        return list(range(n))
    out = set()
    for part in str(spec).replace(" ", "").split(","):
        if not part:
            continue
        m = re.match(r"^(\d+)-(\d+)$", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            out.update(range(min(a, b) - 1, min(max(a, b), n)))
        elif part.isdigit():
            if 1 <= int(part) <= n:
                out.add(int(part) - 1)
    return sorted(out)


def rects_of(page) -> list:
    """쪽 안의 이미지·도형 사각형 목록."""
    R = []
    try:
        for info in page.get_image_info():
            R.append((fitz.Rect(info["bbox"]), "image"))
    except Exception:
        pass
    try:
        for d in page.get_drawings():
            r = d.get("rect")
            if r is not None:
                R.append((fitz.Rect(r), "draw"))
    except Exception:
        pass
    return R


def components(page, rects, page_area):
    """격자 마스크 + 연결요소로 그림 덩어리 bbox 를 구한다."""
    pr = page.rect
    W = max(1, int(pr.width / CELL) + 1)
    H = max(1, int(pr.height / CELL) + 1)
    grid = bytearray(W * H)

    for r, _kind in rects:
        r = r & pr
        if r.is_empty:
            continue
        w, h = r.width, r.height
        if w < 7 and h < 7:                       # 점·자잘한 표식
            continue
        if w * h > page_area * 0.92:              # 배경 판
            continue
        if (w < 2.2 and h > pr.height * 0.5) or (h < 2.2 and w > pr.width * 0.5):
            continue                              # 페이지를 가르는 실선
        x0 = max(0, int((r.x0 - pr.x0) / CELL)); x1 = min(W - 1, int((r.x1 - pr.x0) / CELL))
        y0 = max(0, int((r.y0 - pr.y0) / CELL)); y1 = min(H - 1, int((r.y1 - pr.y0) / CELL))
        for y in range(y0, y1 + 1):
            base = y * W
            for x in range(x0, x1 + 1):
                grid[base + x] = 1

    # 팽창 — 떨어져 있는 조각을 한 그림으로 묶는다
    for _ in range(DILATE):
        nxt = bytearray(grid)
        for y in range(H):
            base = y * W
            for x in range(W):
                if grid[base + x]:
                    continue
                if ((x and grid[base + x - 1]) or (x + 1 < W and grid[base + x + 1])
                        or (y and grid[base - W + x]) or (y + 1 < H and grid[base + W + x])):
                    nxt[base + x] = 1
        grid = nxt

    # 연결요소
    seen = bytearray(W * H)
    out = []
    for i in range(W * H):
        if not grid[i] or seen[i]:
            continue
        q = deque([i]); seen[i] = 1
        mnx = mxx = i % W; mny = mxy = i // W
        cells = 0
        while q:
            j = q.popleft(); cells += 1
            x, y = j % W, j // W
            if x < mnx: mnx = x
            if x > mxx: mxx = x
            if y < mny: mny = y
            if y > mxy: mxy = y
            for k in ((j - 1) if x else -1, (j + 1) if x + 1 < W else -1,
                      (j - W) if y else -1, (j + W) if y + 1 < H else -1):
                if k >= 0 and grid[k] and not seen[k]:
                    seen[k] = 1; q.append(k)
        shrink = DILATE * CELL
        r = fitz.Rect(pr.x0 + mnx * CELL + shrink, pr.y0 + mny * CELL + shrink,
                      pr.x0 + (mxx + 1) * CELL - shrink, pr.y0 + (mxy + 1) * CELL - shrink)
        r = r & pr
        if not r.is_empty:
            out.append((r, cells))
    return out


def text_blocks(page):
    out = []
    for b in page.get_text("blocks"):
        r = fitz.Rect(b[:4])
        t = normalize_text(re.sub(r"\s+", " ", (b[4] or "")).strip())
        if t:
            out.append((r, t))
    return out


def page_title(page, blocks):
    """쪽 상단에서 가장 큰 글자 줄을 제목으로 본다."""
    pr = page.rect
    best, best_sz = "", 0.0
    try:
        for blk in page.get_text("dict")["blocks"]:
            if blk.get("type") != 0:
                continue
            for ln in blk.get("lines", []):
                for sp in ln.get("spans", []):
                    t = normalize_text(re.sub(r"\s+", " ", sp.get("text") or "").strip())
                    if len(t) < 2 or len(t) > 60:
                        continue
                    y = sp["bbox"][1] - pr.y0
                    if y > pr.height * 0.33:
                        continue
                    if sp.get("size", 0) > best_sz:
                        best_sz, best = sp["size"], t
    except Exception:
        pass
    if not best:
        for r, t in blocks:
            if r.y0 - pr.y0 < pr.height * 0.25:
                return t[:60]
    return best


def caption_near(rect, blocks, pr):
    """그림 바로 아래(또는 위)의 짧은 문구 — 캡션 후보."""
    below = [(r, t) for r, t in blocks
             if r.y0 >= rect.y1 - 2 and r.y0 - rect.y1 < 30
             and r.x1 > rect.x0 and r.x0 < rect.x1 and len(t) <= 70]
    if below:
        below.sort(key=lambda p: p[0].y0)
        return below[0][1]
    inside_top = [(r, t) for r, t in blocks
                  if rect.contains(r.tl) and r.y0 - rect.y0 < 26 and len(t) <= 70]
    if inside_top:
        inside_top.sort(key=lambda p: p[0].y0)
        return inside_top[0][1]
    return ""


def ink_ratio(page, rect) -> float:
    """잘라낼 영역에 실제로 그려진 것이 얼마나 있는지(0~1).

    발표자료에는 내용 없는 빈 박스·배경 패널이 흔하다. 저해상도로 한 번 더
    렌더해서 가장 많은 색(배경)과 다른 픽셀 비율을 재면 싸게 걸러낼 수 있다.
    """
    try:
        pm = page.get_pixmap(dpi=24, clip=rect, colorspace=fitz.csGRAY)
    except Exception:
        return 1.0
    buf = pm.samples
    if not buf:
        return 0.0
    hist = [0] * 256
    for b in buf:
        hist[b] += 1
    bg = hist.index(max(hist))
    ink = sum(n for v, n in enumerate(hist) if abs(v - bg) > 12)
    return ink / len(buf)


def expand_with_text(rect, blocks, pr):
    """그림 안쪽 글자(라벨)를 품도록 bbox 를 살짝 넓힌다."""
    out = fitz.Rect(rect)
    for r, _t in blocks:
        inter = fitz.Rect(r) & rect
        if inter.is_empty:
            continue
        if inter.get_area() >= r.get_area() * 0.55:      # 절반 넘게 겹치면 그림의 일부
            out |= r
    out = fitz.Rect(out.x0 - PAD, out.y0 - PAD, out.x1 + PAD, out.y1 + PAD) & pr
    return out


# ------------------------------------------------------------------ main ----
def main():
    ap = argparse.ArgumentParser(description="발표자료 PDF → 텍스트 + 그림 후보 추출")
    ap.add_argument("pdf")
    ap.add_argument("-o", "--out", default="_추출", help="출력 폴더")
    ap.add_argument("--pages", default="", help='쪽 범위 예) "3-20,25"')
    ap.add_argument("--dpi", type=int, default=170, help="그림 후보 해상도")
    ap.add_argument("--page-dpi", type=int, default=72, help="쪽 전체 렌더 해상도")
    ap.add_argument("--min-area", type=float, default=0.045,
                    help="쪽 면적 대비 최소 비율(이보다 작으면 로고·장식으로 보고 버림)")
    ap.add_argument("--max-area", type=float, default=0.88, help="최대 비율")
    ap.add_argument("--max", type=int, default=60, help="그림 후보 최대 개수")
    ap.add_argument("--min-ink", type=float, default=0.012,
                    help="이보다 그려진 것이 적으면 빈 박스로 보고 버림(0~1)")
    ap.add_argument("--min-text", type=int, default=30,
                    help="이보다 글자가 적은 쪽은 간지로 보고 그림을 뽑지 않음")
    ap.add_argument("--no-pages", action="store_true", help="쪽 전체 렌더 생략")
    a = ap.parse_args()

    src = Path(a.pdf)
    if not src.exists():
        raise SystemExit(f"[ERROR] 파일 없음: {src}")
    out = Path(a.out)
    (out / "pages").mkdir(parents=True, exist_ok=True)

    doc = fitz.open(src)
    idx = parse_pages(a.pages, doc.page_count)
    figures, md = [], [f"# {src.name}", "",
                       f"총 {doc.page_count}쪽 · 추출 대상 {len(idx)}쪽", ""]

    for pno in idx:
        page = doc[pno]
        pr = page.rect
        parea = pr.width * pr.height
        blocks = text_blocks(page)
        title = page_title(page, blocks)
        body = normalize_text(page.get_text().strip())
        # 간지(섹션 구분) 쪽 — 글자가 거의 없으면 장식뿐이므로 그림을 뽑지 않는다
        divider = len(re.sub(r"[\s\d]", "", body)) < a.min_text

        cands = []
        for rect, _cells in (() if divider else
                             components(page, rects_of(page), parea)):
            ratio = rect.get_area() / parea
            if ratio < a.min_area or ratio > a.max_area:
                continue
            if rect.width < 55 or rect.height < 40:
                continue
            if (rect.y1 - pr.y0) < pr.height * 0.14 and ratio < 0.12:
                continue                                      # 머리글 장식
            cands.append(expand_with_text(rect, blocks, pr))

        # 많이 겹치는 것은 큰 쪽만 남긴다
        cands.sort(key=lambda r: -r.get_area())
        kept = []
        for r in cands:
            if any((r & k).get_area() >= r.get_area() * 0.75 for k in kept):
                continue
            kept.append(r)

        kept = [r for r in kept if ink_ratio(page, r) >= a.min_ink]
        page_figs = []
        for i, r in enumerate(kept, 1):
            if len(figures) >= a.max:
                break
            name = f"fig_p{pno+1:02d}_{i}.png"
            pix = page.get_pixmap(dpi=a.dpi, clip=r)
            pix.save(out / name)
            rec = {"id": name[:-4], "file": name, "page": pno + 1,
                   "rect": [round(v, 1) for v in (r.x0, r.y0, r.x1, r.y1)],
                   "w_px": pix.width, "h_px": pix.height,
                   "area_ratio": round(r.get_area() / parea, 3),
                   "page_title": title, "caption_hint": caption_near(r, blocks, pr),
                   "page_text_len": len(body),
                   "ink": round(ink_ratio(page, r), 4)}
            figures.append(rec)
            page_figs.append(rec)

        if not a.no_pages:
            page.get_pixmap(dpi=a.page_dpi).save(out / "pages" / f"p{pno+1:02d}.png")

        md.append(f"## {pno+1}쪽" + (f" — {title}" if title else "")
                  + ("  *(간지)*" if divider else ""))
        if body:
            md.append("```")
            md.append(body[:2500])
            md.append("```")
        for rec in page_figs:
            md.append(f"- 그림 후보 `{rec['file']}` "
                      f"({rec['w_px']}×{rec['h_px']}px, 쪽 면적의 {int(rec['area_ratio']*100)}%)"
                      + (f" — 주변 문구: {rec['caption_hint']}" if rec["caption_hint"] else ""))
        md.append("")

    md_text = "\n".join(md)
    leftovers = {}
    for ch in _RARE.findall(md_text):
        leftovers[ch] = leftovers.get(ch, 0) + 1

    (out / "figures.json").write_text(
        json.dumps(figures, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "text.md").write_text("\n".join(md), encoding="utf-8")
    doc.close()

    print(json.dumps({
        "pdf": str(src), "out": str(out.resolve()),
        "pages_total": len(idx), "figures": len(figures),
        "text_md": str((out / "text.md").resolve()),
        "figures_json": str((out / "figures.json").resolve()),
        "by_page": {str(p): sum(1 for f in figures if f["page"] == p)
                    for p in sorted({f["page"] for f in figures})},
        "unknown_glyphs": leftovers or None,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
