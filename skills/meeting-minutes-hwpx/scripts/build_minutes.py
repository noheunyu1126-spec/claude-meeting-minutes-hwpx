# -*- coding: utf-8 -*-


"""


회의록(HWPX) 생성기 — ○○대 ○○본부 간담회 회의록 양식





assets/template.hwpx(원본 「회의록」 양식)의 header.xml/settings.xml/Preview/secPr 를


그대로 재사용하고, Contents/section0.xml 의


  - 제목표 값 셀(제 목·일 시·작성자·장 소·관리자·참석자)


  - 본문 셀(■ 회의 내용 아래 큰 셀)


만 콘텐츠 JSON 으로 다시 채운다. 서식 자원은 원본 그대로이므로 글꼴·여백·테두리·


색상이 양식과 100% 일치한다.





사용법:


    python build_minutes.py -c content.json [-o 결과.hwpx] [--pdf]


    python build_minutes.py --schema         # 스키마 출력


    python build_minutes.py --selftest       # 더미 콘텐츠로 빌드 검증


"""


from __future__ import annotations





import argparse


import json


import math


import re


import struct


import sys


import zipfile


from pathlib import Path





from lxml import etree





try:                                        # Windows cp949 콘솔 대응


    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


except Exception:


    pass





# ---------------------------------------------------------------- 상수/자원 --


HERE = Path(__file__).resolve().parent


TEMPLATE = HERE.parent / "assets" / "template.hwpx"





HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


HC = "http://www.hancom.co.kr/hwpml/2011/core"


HH = "http://www.hancom.co.kr/hwpml/2011/head"


NSMAP = {


    "ha": "http://www.hancom.co.kr/hwpml/2011/app",


    "hp": HP,


    "hp10": "http://www.hancom.co.kr/hwpml/2016/paragraph",


    "hs": "http://www.hancom.co.kr/hwpml/2011/section",


    "hc": HC,


    "hh": HH,


    "hhs": "http://www.hancom.co.kr/hwpml/2011/history",


    "hm": "http://www.hancom.co.kr/hwpml/2011/master-page",


    "hpf": "http://www.hancom.co.kr/schema/2011/hpf",


    "dc": "http://purl.org/dc/elements/1.1/",


    "opf": "http://www.idpf.org/2007/opf/",


    "ooxmlchart": "http://www.hancom.co.kr/hwpml/2016/ooxmlchart",


    "hwpunitchar": "http://www.hancom.co.kr/hwpml/2016/HwpUnitChar",


    "epub": "http://www.idpf.org/2007/ops",


    "config": "urn:oasis:names:tc:opendocument:xmlns:config:1.0",


}


NSDECL = " ".join(f'xmlns:{k}="{v}"' for k, v in NSMAP.items())





# --- 원본 양식이 이미 가지고 있는 자원 ID -----------------------------------


CP_TITLE_VAL = "30"   # 제 목 값 : 맑은 고딕 12pt


CP_HDR_VAL = "13"     # 일시/장소 값 : 맑은 고딕 12pt


CP_HDR_NAME = "12"    # 작성자/관리자 값 : 맑은 고딕 11pt


CP_H1 = "28"          # 1. 절 표제 : 휴먼명조 14pt 굵게


CP_BODY = "31"        # 본문 : 휴먼명조 12pt


CP_NOTE = "32"        # ※ 단서 : 휴먼명조 10pt


PP_TITLE_VAL = "27"   # 제 목 값 문단(가운데)


PP_HDR_VAL = "19"     # 일시/작성자 등 값 문단(가운데)


PP_H1 = "36"          # 1. 절 표제 문단


PP_B1 = "37"          # ◦ 글머리 문단


PP_NOTE_T = "38"      # ※ 단서 문단(원본)


PP_CENTER = "7"       # 가운데 정렬(그림 셀)


BF_CELL = "5"         # 표 본문 셀(실선 0.12mm)


BF_INVIS = "16"       # 테두리 없는 셀(그림 담는 표)


BF_SHADE = "13"       # 음영 셀(#F2F2F2, 합계행 등)





# --- 이 스킬이 header.xml 에 추가하는 자원 ID -------------------------------


BF_THEAD = "17"       # 표 머리행(연청 #DAE3F3)


CP_LABEL = "33"       # (라벨) : 휴먼명조 12pt 굵게


CP_H2 = "34"          # 가. 소제목 : 휴먼명조 13pt 굵게


CP_THEAD = "35"       # 표 머리행 글자 : 맑은 고딕 10pt 굵게


CP_TBODY = "36"       # 표 본문 글자 : 맑은 고딕 10pt


CP_CAPTION = "37"     # 그림 캡션 : 휴먼명조 11pt


CP_TOPIC = "38"       # □ 대주제 : 휴먼명조 15pt 굵게


CP_ATTEND = "39"      # 참석자 : 맑은 고딕 11pt


CP_LABEL_S = "40"     # 하위 글머리 (라벨) : 휴먼명조 12pt 굵게(= 33 과 동일 폭)





PP_H2 = "41"          # 가. 소제목


PP_B2 = "42"          # - 하위 글머리


PP_B3 = "43"          # ○ 세부 글머리


PP_CAPTION = "44"     # 그림 캡션(가운데)


PP_TCELL_C = "45"     # 표 셀 가운데


PP_TCELL_L = "46"     # 표 셀 왼쪽


PP_ATTEND = "47"      # 참석자 셀


PP_TOPIC = "48"       # □ 대주제


PP_BLOCK = "49"       # 표/그림을 담는 문단(가운데)


PP_NOTE = "50"        # ※ 단서(◦ 본문 위치에 맞춤)





# 본문 셀 안쪽에서 실제로 쓸 수 있는 폭(HWPUNIT)


BODY_TEXT_WIDTH = 46068


TABLE_WIDTH = 44500        # 본문 표 기본 전체 폭


TABLE_IN_MARGIN = 141      # 표 셀 안쪽 여백


IMAGE_TABLE_WIDTH = 43000  # 그림 담는 표 기본 전체 폭








# ------------------------------------------------------------------ 유틸 ----


_idc = [1900000000]








def nid() -> str:


    _idc[0] += 7


    return str(_idc[0])








def esc(t) -> str:


    if t is None:


        return ""


    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


            .replace('"', "&quot;"))








def textwidth(s: str, pt: int) -> int:


    """문자열의 대략적인 렌더 폭(HWPUNIT). 전각=1em, 반각=0.5em."""


    em = pt * 100


    w = 0


    for ch in str(s):


        o = ord(ch)


        wide = (0x1100 <= o <= 0x115F or 0x2E80 <= o <= 0xA4CF or 0xAC00 <= o <= 0xD7A3


                or 0xF900 <= o <= 0xFAFF or 0xFE30 <= o <= 0xFE4F


                or 0xFF00 <= o <= 0xFF60 or 0xFFE0 <= o <= 0xFFE6


                or ch in "◦○□■※·→←↔①②③④⑤⑥⑦⑧⑨⑩「」『』")


        w += em if wide else em // 2


    return w








def nlines(s: str, pt: int, avail: int) -> int:


    if avail <= 0:


        return 1


    return max(1, math.ceil(textwidth(s, pt) / avail))








def auto_widths(grid, ncol: int):


    """표 열 폭을 내용 길이에 맞춰 자동 배분(상대 비율)."""


    out = []


    for c in range(ncol):


        w = 0


        for r in grid:


            v = str(r[c]) if c < len(r) else ""


            if v.strip() == "^":


                continue


            w = max(w, max(textwidth(x, 10) for x in v.split("\n")))


        out.append(max(4200, min(w + 900, 26000)))


    return out








def auto_align(grid, ncol: int, widths):


    """한 줄에 들어가는 짧은 열은 가운데, 줄바꿈이 생기는 열은 왼쪽 정렬."""


    out = []


    for c in range(ncol):


        avail = widths[c] - 2 * TABLE_IN_MARGIN - 200


        wrapped = any(


            nlines(str(r[c]) if c < len(r) else "", 10, avail) > 1 for r in grid[1:])


        out.append("left" if (wrapped and c > 0) else "center")


    return out








def lineseg(horzpos: int, horzsize: int, h: int) -> str:


    return ('<hp:linesegarray><hp:lineseg textpos="0" vertpos="0" '


            f'vertsize="{h}" textheight="{h}" baseline="{int(h * 0.85)}" '


            f'spacing="{int(h * 0.6)}" horzpos="{horzpos}" horzsize="{horzsize}" '


            'flags="393216"/></hp:linesegarray>')








# -------------------------------------------------------- 인라인 굵게 처리 --


def runs_of(text: str, cp: str, cp_bold: str) -> str:


    """`**굵게**` 마커와 선행 `(라벨)` 을 굵은 run 으로 분리."""


    text = "" if text is None else str(text)


    out = []


    parts = re.split(r"\*\*(.+?)\*\*", text)


    for i, seg in enumerate(parts):


        if not seg:


            continue


        if i % 2 == 1:


            out.append(f'<hp:run charPrIDRef="{cp_bold}"><hp:t>{esc(seg)}</hp:t></hp:run>')


        else:


            out.extend(_auto_label_runs(seg, cp, cp_bold))


    if not out:


        out.append(f'<hp:run charPrIDRef="{cp}"><hp:t></hp:t></hp:run>')


    return "".join(out)








def _auto_label_runs(seg: str, cp: str, cp_bold: str):


    """문단 맨 앞의 `(라벨)` 을 자동으로 굵게."""


    m = re.match(r"^(\s*)(\([^()]{1,30}\))(.*)$", seg, re.S)


    if not m:


        return [f'<hp:run charPrIDRef="{cp}"><hp:t>{esc(seg)}</hp:t></hp:run>']


    pre, label, rest = m.groups()


    runs = []


    if pre:


        runs.append(f'<hp:run charPrIDRef="{cp}"><hp:t>{esc(pre)}</hp:t></hp:run>')


    runs.append(f'<hp:run charPrIDRef="{cp_bold}"><hp:t>{esc(label)}</hp:t></hp:run>')


    if rest:


        runs.append(f'<hp:run charPrIDRef="{cp}"><hp:t>{esc(rest)}</hp:t></hp:run>')


    return runs








def para(ppr: str, runs_xml: str, horzpos: int, pt: int, width: int | None = None) -> str:


    w = BODY_TEXT_WIDTH - horzpos if width is None else width


    return (f'<hp:p id="{nid()}" paraPrIDRef="{ppr}" styleIDRef="0" pageBreak="0" '


            f'columnBreak="0" merged="0">{runs_xml}{lineseg(horzpos, w, pt * 100)}</hp:p>')








def simple_para(ppr: str, cp: str, text: str, horzpos: int, pt: int,


                cp_bold: str | None = None) -> str:


    return para(ppr, runs_of(text, cp, cp_bold or cp), horzpos, pt)








# --------------------------------------------------------- 본문 블록 생성 ---


class Doc:


    """본문 셀(r7c0) 안에 들어갈 문단들을 조립한다."""





    def __init__(self, images_dir: Path | None):


        self.parts: list[str] = []


        self.images: list[tuple[str, bytes, str]] = []   # (id, bytes, media-type)


        self.height = 0          # 본문 셀 높이 추정치(HWPUNIT)


        self.plain: list[str] = []


        self.images_dir = images_dir


        self._auto_sec = 0





    # ---- 텍스트 -----------------------------------------------------------


    def _add(self, xml: str, h: int, plain: str = ""):


        self.parts.append(xml)


        self.height += h


        if plain:


            self.plain.append(plain)





    def topic(self, text: str):


        t = f"□ {text}"


        self._add(simple_para(PP_TOPIC, CP_TOPIC, t, 500, 15, CP_TOPIC),


                  nlines(t, 15, BODY_TEXT_WIDTH - 500) * 2400 + 1000, t)





    def heading(self, num: int, text: str):


        t = f"{num}. {text}"


        self._add(simple_para(PP_H1, CP_H1, t, 500, 14, CP_H1),


                  nlines(t, 14, BODY_TEXT_WIDTH - 500) * 2240 + 1000, "\n" + t)





    def subheading(self, marker: str, text: str):


        t = f"{marker} {text}"


        self._add(simple_para(PP_H2, CP_H2, t, 1100, 13, CP_H2),


                  nlines(t, 13, BODY_TEXT_WIDTH - 1100) * 2080 + 700, " " + t)





    def _marked(self, mark: str, text: str, label: str | None, ppr: str,


                horzpos: int, wrap_at: int, gap: int, indent: str):


        """`mark (라벨) 본문` 한 문단. mark 는 보통 글꼴, (라벨) 만 굵게."""


        body = f"({label}) {text}" if label else ("" if text is None else str(text))


        runs = (f'<hp:run charPrIDRef="{CP_BODY}"><hp:t>{esc(mark + " ")}</hp:t>'


                f'</hp:run>' + runs_of(body, CP_BODY, CP_LABEL))


        t = f"{mark} {body}"


        self._add(para(ppr, runs, horzpos, 12),


                  nlines(t, 12, BODY_TEXT_WIDTH - wrap_at) * 1920 + gap,


                  indent + t)





    def bullet(self, text: str, label: str | None = None):


        self._marked("◦", text, label, PP_B1, 1100, 2900, 1000, " ")





    def subbullet(self, text: str, label: str | None = None):


        self._marked("-", text, label, PP_B2, 2900, 4100, 400, "   ")





    def subsub(self, text: str, label: str | None = None):


        self._marked("○", text, label, PP_B3, 4100, 5900, 300, "     ")





    def note(self, text: str):


        t = f"※ {text}"


        self._add(simple_para(PP_NOTE, CP_NOTE, t, 2900, 10, CP_NOTE),


                  nlines(t, 10, BODY_TEXT_WIDTH - 4400) * 1600 + 500, "   " + t)





    def spacer(self):


        self._add(para(PP_B1, f'<hp:run charPrIDRef="{CP_BODY}"><hp:t></hp:t></hp:run>',


                       1100, 12), 1900)





    # ---- 표 ---------------------------------------------------------------


    def table(self, headers, rows, widths=None, align=None, total_width=None,


              caption=None, shade_rows=None, total_row=False):


        rows = [list(r) for r in rows]


        ncol = len(headers) if headers else (len(rows[0]) if rows else 1)


        total = total_width or TABLE_WIDTH


        grid0 = ([list(headers)] if headers else []) + rows


        if not widths:


            widths = auto_widths(grid0, ncol)          # 내용 길이에 맞춰 자동 배분


        s = float(sum(widths)) or 1.0


        widths = [int(round(w / s * total)) for w in widths]


        widths[-1] = total - sum(widths[:-1])


        if not align:


            align = auto_align(grid0, ncol, widths)    # 짧은 열은 가운데, 긴 열은 왼쪽


        align = (list(align) + ["left"] * ncol)[:ncol]





        grid = grid0


        nrow = len(grid)


        off = 1 if headers else 0


        shaded = {int(i) + off for i in (shade_rows or [])}


        if total_row and rows:


            shaded.add(nrow - 1)





        # 세로 병합("^") 계산


        span = [[1] * ncol for _ in range(nrow)]


        hidden = [[False] * ncol for _ in range(nrow)]


        for c in range(ncol):


            r = 0


            while r < nrow:


                if r + 1 < nrow and str(grid[r][c]).strip() == "^":


                    r += 1


                    continue


                k = r + 1


                while k < nrow and str(grid[k][c]).strip() == "^":


                    hidden[k][c] = True


                    k += 1


                span[r][c] = k - r


                r = k





        # 행 높이 추정


        rheights = []


        for r in range(nrow):


            pt = 10


            mx = 1


            for c in range(ncol):


                if hidden[r][c]:


                    continue


                avail = widths[c] - 2 * TABLE_IN_MARGIN - 200


                mx = max(mx, nlines(str(grid[r][c]), pt, avail))


            rheights.append(mx * 1700 + 500)


        theight = sum(rheights)





        # 셀 조립


        trs = []


        for r in range(nrow):


            tcs = []


            for c in range(ncol):


                if hidden[r][c]:


                    continue


                is_head = bool(headers) and r == 0


                bf = BF_THEAD if is_head else (BF_SHADE if r in shaded else BF_CELL)


                cp = CP_THEAD if (is_head or r in shaded) else CP_TBODY


                a = "center" if (is_head or r in shaded) else align[c]


                ppr = PP_TCELL_C if a == "center" else PP_TCELL_L


                txt = "" if str(grid[r][c]).strip() == "^" else str(grid[r][c])


                cellw = widths[c]


                cellh = sum(rheights[r:r + span[r][c]])


                inner = cellw - 2 * TABLE_IN_MARGIN


                body = ""


                for i, line in enumerate(str(txt).split("\n")):


                    body += para(ppr, runs_of(line, cp, CP_THEAD), 0, 10, inner)


                tcs.append(


                    f'<hp:tc name="" header="{1 if is_head else 0}" hasMargin="0" '


                    f'protect="0" editable="0" dirty="0" borderFillIDRef="{bf}">'


                    f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '


                    f'vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" '


                    f'textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'


                    f'{body}</hp:subList>'


                    f'<hp:cellAddr colAddr="{c}" rowAddr="{r}"/>'


                    f'<hp:cellSpan colSpan="1" rowSpan="{span[r][c]}"/>'


                    f'<hp:cellSz width="{cellw}" height="{cellh}"/>'


                    f'<hp:cellMargin left="{TABLE_IN_MARGIN}" right="{TABLE_IN_MARGIN}" '


                    f'top="{TABLE_IN_MARGIN}" bottom="{TABLE_IN_MARGIN}"/></hp:tc>')


            trs.append("<hp:tr>" + "".join(tcs) + "</hp:tr>")





        tbl = (f'<hp:tbl id="{nid()}" zOrder="0" numberingType="TABLE" '


               f'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" '


               f'dropcapstyle="None" pageBreak="CELL" repeatHeader="1" '


               f'rowCnt="{nrow}" colCnt="{ncol}" cellSpacing="0" '


               f'borderFillIDRef="{BF_CELL}" noAdjust="0">'


               f'<hp:sz width="{total}" widthRelTo="ABSOLUTE" height="{theight}" '


               f'heightRelTo="ABSOLUTE" protect="0"/>'


               f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" '


               f'allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="PARA" '


               f'vertAlign="TOP" horzAlign="CENTER" vertOffset="0" horzOffset="0"/>'


               f'<hp:outMargin left="283" right="283" top="283" bottom="283"/>'


               f'<hp:inMargin left="{TABLE_IN_MARGIN}" right="{TABLE_IN_MARGIN}" '


               f'top="{TABLE_IN_MARGIN}" bottom="{TABLE_IN_MARGIN}"/>'


               + "".join(trs) + "</hp:tbl>")





        self._add(f'<hp:p id="{nid()}" paraPrIDRef="{PP_BLOCK}" styleIDRef="0" '


                  f'pageBreak="0" columnBreak="0" merged="0">'


                  f'<hp:run charPrIDRef="{CP_BODY}">{tbl}</hp:run>'


                  + lineseg(500, BODY_TEXT_WIDTH - 500, theight + 566) + "</hp:p>",


                  theight + 900)


        self.plain.append("[표] " + " / ".join(str(h) for h in (headers or [])))


        if caption:


            self.caption(caption)





    # ---- 그림 -------------------------------------------------------------


    def caption(self, text: str):


        t = f"[{text}]" if not str(text).startswith("[") else str(text)


        self._add(simple_para(PP_CAPTION, CP_CAPTION, t, 500, 11),


                  nlines(t, 11, BODY_TEXT_WIDTH - 500) * 1760 + 200, t)





    def image_row(self, files, captions=None, total_width=None, max_height=None):


        files = [files] if isinstance(files, str) else list(files)


        captions = list(captions or [])


        ncol = max(1, len(files))


        total = total_width or IMAGE_TABLE_WIDTH


        cw = total // ncol


        inner = cw - 2 * 510 - 300          # 셀 안쪽 여백 + 여유폭





        cells, cap_cells, rowh = [], [], 0


        for i, f in enumerate(files):


            path = self._resolve(f)


            raw = path.read_bytes()


            px_w, px_h = image_size(raw, path.suffix)


            mt = media_type(path.suffix)


            iid = f"image{len(self.images) + 1}"


            self.images.append((iid + path.suffix.lower(), raw, mt))


            ow, oh = px_w * 75, px_h * 75          # 96dpi px -> HWPUNIT


            dw = min(inner, ow)


            dh = int(round(oh * dw / ow)) if ow else inner


            cap = max_height or 30000


            if dh > cap:


                dw = int(round(dw * cap / dh)); dh = cap


            rowh = max(rowh, dh + 1100)


            pic = (f'<hp:pic id="{nid()}" zOrder="{i}" numberingType="PICTURE" '


                   f'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" '


                   f'dropcapstyle="None" href="" groupLevel="0" instid="{nid()}" '


                   f'reverse="0"><hp:offset x="0" y="0"/>'


                   f'<hp:orgSz width="{ow}" height="{oh}"/>'


                   f'<hp:curSz width="{dw}" height="{dh}"/>'


                   f'<hp:flip horizontal="0" vertical="0"/>'


                   f'<hp:rotationInfo angle="0" centerX="{dw // 2}" centerY="{dh // 2}" '


                   f'rotateimage="1"/><hp:renderingInfo>'


                   f'<hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'


                   f'<hc:scaMatrix e1="{dw / ow if ow else 1:.6f}" e2="0" e3="0" e4="0" '


                   f'e5="{dh / oh if oh else 1:.6f}" e6="0"/>'


                   f'<hc:rotMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'


                   f'</hp:renderingInfo>'


                   f'<hc:img binaryItemIDRef="{iid}" bright="0" contrast="0" '


                   f'effect="REAL_PIC" alpha="0"/>'


                   # 렌더 크기 = imgRect x (curSz / orgSz) -> imgRect 는 원본 크기


                   f'<hp:imgRect><hc:pt0 x="0" y="0"/><hc:pt1 x="{ow}" y="0"/>'


                   f'<hc:pt2 x="{ow}" y="{oh}"/><hc:pt3 x="0" y="{oh}"/></hp:imgRect>'


                   f'<hp:imgClip left="0" right="{ow}" top="0" bottom="{oh}"/>'


                   f'<hp:inMargin left="0" right="0" top="0" bottom="0"/>'


                   f'<hp:imgDim dimwidth="{ow}" dimheight="{oh}"/><hp:effects/>'


                   f'<hp:sz width="{dw}" widthRelTo="ABSOLUTE" height="{dh}" '


                   f'heightRelTo="ABSOLUTE" protect="0"/>'


                   f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" '


                   f'allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" '


                   f'horzRelTo="PARA" vertAlign="TOP" horzAlign="CENTER" '


                   f'vertOffset="0" horzOffset="0"/>'


                   f'<hp:outMargin left="0" right="0" top="0" bottom="0"/></hp:pic>')


            cells.append(self._invis_cell(


                i, 0, cw, rowh,


                f'<hp:p id="{nid()}" paraPrIDRef="{PP_CENTER}" styleIDRef="0" '


                f'pageBreak="0" columnBreak="0" merged="0">'


                f'<hp:run charPrIDRef="1">{pic}</hp:run>'


                + lineseg(0, inner, dh) + "</hp:p>"))


            ctext = captions[i] if i < len(captions) else ""


            if ctext and not str(ctext).startswith("["):


                ctext = f"[{ctext}]"


            cap_cells.append(self._invis_cell(


                i, 1, cw, 1900,


                para(PP_CENTER, runs_of(ctext, CP_CAPTION, CP_CAPTION), 0, 11, inner)))





        has_cap = any(captions)


        trs = ["<hp:tr>" + "".join(cells) + "</hp:tr>"]


        if has_cap:


            trs.append("<hp:tr>" + "".join(cap_cells) + "</hp:tr>")


        th = rowh + (1900 if has_cap else 0)


        tbl = (f'<hp:tbl id="{nid()}" zOrder="0" numberingType="TABLE" '


               f'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" '


               f'dropcapstyle="None" pageBreak="CELL" repeatHeader="0" '


               f'rowCnt="{2 if has_cap else 1}" colCnt="{ncol}" cellSpacing="0" '


               f'borderFillIDRef="{BF_INVIS}" noAdjust="0">'


               f'<hp:sz width="{total}" widthRelTo="ABSOLUTE" height="{th}" '


               f'heightRelTo="ABSOLUTE" protect="0"/>'


               f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" '


               f'allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="PARA" '


               f'vertAlign="TOP" horzAlign="CENTER" vertOffset="0" horzOffset="0"/>'


               f'<hp:outMargin left="283" right="283" top="283" bottom="283"/>'


               f'<hp:inMargin left="510" right="510" top="141" bottom="141"/>'


               + "".join(trs) + "</hp:tbl>")


        self._add(f'<hp:p id="{nid()}" paraPrIDRef="{PP_BLOCK}" styleIDRef="0" '


                  f'pageBreak="0" columnBreak="0" merged="0">'


                  f'<hp:run charPrIDRef="{CP_BODY}">{tbl}</hp:run>'


                  + lineseg(500, BODY_TEXT_WIDTH - 500, th + 566) + "</hp:p>",


                  th + 900)


        self.plain.append("[그림] " + ", ".join(str(c) for c in captions if c))





    def _invis_cell(self, c, r, w, h, body):


        return (f'<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" '


                f'dirty="0" borderFillIDRef="{BF_INVIS}">'


                f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '


                f'vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" '


                f'textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">{body}'


                f'</hp:subList><hp:cellAddr colAddr="{c}" rowAddr="{r}"/>'


                f'<hp:cellSpan colSpan="1" rowSpan="1"/>'


                f'<hp:cellSz width="{w}" height="{h}"/>'


                f'<hp:cellMargin left="510" right="510" top="141" bottom="141"/></hp:tc>')





    def _resolve(self, f) -> Path:


        p = Path(str(f)).expanduser()


        if not p.is_absolute() and self.images_dir:


            cand = self.images_dir / p


            if cand.exists():


                return cand


        if not p.exists():


            raise SystemExit(f"[ERROR] 이미지 파일을 찾을 수 없음: {f}")


        return p





    # ---- 블록 디스패치 -----------------------------------------------------


    def render(self, blocks):


        for b in blocks or []:


            if isinstance(b, str):


                self.bullet(b)


                continue


            t = (b.get("type") or "bullet").lower()


            if t in ("bullet", "b1", "o"):


                self.bullet(b.get("text", ""), b.get("label"))


            elif t in ("subbullet", "b2", "dash"):


                self.subbullet(b.get("text", ""), b.get("label"))


            elif t in ("subsub", "b3", "circle"):


                self.subsub(b.get("text", ""), b.get("label"))


            elif t in ("subheading", "h2", "ga"):


                self.subheading(b.get("marker") or self._next_ga(), b.get("text", ""))


            elif t in ("note", "footnote"):


                self.note(b.get("text", ""))


            elif t == "topic":


                self.topic(b.get("text", ""))


            elif t == "spacer":


                self.spacer()


            elif t == "table":


                self.table(b.get("headers"), b.get("rows") or [], b.get("widths"),


                           b.get("align"), b.get("total_width"), b.get("caption"),


                           b.get("shade_rows"), bool(b.get("total_row")))


            elif t in ("image", "images", "figure"):


                self.image_row(b.get("files") or b.get("file") or [],


                               b.get("captions") or ([b["caption"]] if b.get("caption") else None),


                               b.get("total_width"), b.get("max_height"))


            elif t == "caption":


                self.caption(b.get("text", ""))


            else:


                raise SystemExit(f"[ERROR] 알 수 없는 block type: {t!r}")





    def _next_ga(self):


        ga = "가나다라마바사아자차카타파하"


        self._auto_sec += 1


        return ga[(self._auto_sec - 1) % len(ga)] + "."








# --------------------------------------------------- 이미지 크기/미디어타입 --


def media_type(suffix: str) -> str:


    return {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",


            ".gif": "image/gif", ".bmp": "image/bmp", ".tif": "image/tiff",


            ".tiff": "image/tiff", ".wmf": "image/wmf", ".emf": "image/emf",


            ".svg": "image/svg+xml"}.get(suffix.lower(), "image/png")








def image_size(raw: bytes, suffix: str):


    try:


        from PIL import Image          # noqa


        import io as _io


        with Image.open(_io.BytesIO(raw)) as im:


            return im.size


    except Exception:


        pass


    s = suffix.lower()


    try:


        if s == ".png" and raw[:8] == b"\x89PNG\r\n\x1a\n":


            return struct.unpack(">II", raw[16:24])


        if s == ".bmp" and raw[:2] == b"BM":


            w, h = struct.unpack("<ii", raw[18:26])


            return abs(w), abs(h)


        if s == ".gif":


            return struct.unpack("<HH", raw[6:10])


        if s in (".jpg", ".jpeg"):


            i = 2


            while i < len(raw) - 9:


                if raw[i] != 0xFF:


                    i += 1


                    continue


                m = raw[i + 1]


                if 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):


                    h, w = struct.unpack(">HH", raw[i + 5:i + 9])


                    return w, h


                i += 2 + struct.unpack(">H", raw[i + 2:i + 4])[0]


    except Exception:


        pass


    return 1000, 600








# ------------------------------------------------------- header.xml 확장 ----


def _charpr(i, h, font, bold=False, spacing=0, color="#000000", bfref="4"):


    b = "<hh:bold/>" if bold else ""


    fr = (f'<hh:fontRef hangul="{font}" latin="{font}" hanja="{font}" '


          f'japanese="{font}" other="{font}" symbol="{font}" user="{font}"/>')


    sp = (f'<hh:spacing hangul="{spacing}" latin="{spacing}" hanja="{spacing}" '


          f'japanese="{spacing}" other="{spacing}" symbol="{spacing}" user="{spacing}"/>')


    return (f'<hh:charPr id="{i}" height="{h}" textColor="{color}" shadeColor="none" '


            f'useFontSpace="0" useKerning="0" symMark="NONE" borderFillIDRef="{bfref}">'


            f'{fr}<hh:ratio hangul="100" latin="100" hanja="100" japanese="100" '


            f'other="100" symbol="100" user="100"/>{sp}'


            f'<hh:relSz hangul="100" latin="100" hanja="100" japanese="100" other="100" '


            f'symbol="100" user="100"/><hh:offset hangul="0" latin="0" hanja="0" '


            f'japanese="0" other="0" symbol="0" user="0"/>{b}'


            f'<hh:underline type="NONE" shape="SOLID" color="#000000"/>'


            f'<hh:strikeout shape="NONE" color="#000000"/><hh:outline type="NONE"/>'


            f'<hh:shadow type="NONE" color="#B2B2B2" offsetX="10" offsetY="10"/>'


            f'</hh:charPr>')








def _parapr(i, align, left=0, right=0, intent=0, prev=0, nxt=0, spacing=160,


            bfref="2"):


    def margin(f):


        return ('<hh:margin>'


                f'<hc:intent value="{int(intent * f)}" unit="HWPUNIT"/>'


                f'<hc:left value="{int(left * f)}" unit="HWPUNIT"/>'


                f'<hc:right value="{int(right * f)}" unit="HWPUNIT"/>'


                f'<hc:prev value="{int(prev * f)}" unit="HWPUNIT"/>'


                f'<hc:next value="{int(nxt * f)}" unit="HWPUNIT"/></hh:margin>'


                f'<hh:lineSpacing type="PERCENT" value="{spacing}" unit="HWPUNIT"/>')


    return (f'<hh:paraPr id="{i}" tabPrIDRef="0" condense="0" fontLineHeight="0" '


            f'snapToGrid="1" suppressLineNumbers="0" checked="0">'


            f'<hh:align horizontal="{align}" vertical="BASELINE"/>'


            f'<hh:heading type="NONE" idRef="0" level="0"/>'


            f'<hh:breakSetting breakLatinWord="KEEP_WORD" breakNonLatinWord="KEEP_WORD" '


            f'widowOrphan="0" keepWithNext="0" keepLines="0" pageBreakBefore="0" '


            f'lineWrap="BREAK"/><hh:autoSpacing eAsianEng="0" eAsianNum="0"/>'


            f'<hp:switch><hp:case hp:required-namespace='


            f'"http://www.hancom.co.kr/hwpml/2016/HwpUnitChar">{margin(1)}</hp:case>'


            f'<hp:default>{margin(2)}</hp:default></hp:switch>'


            f'<hh:border borderFillIDRef="{bfref}" offsetLeft="0" offsetRight="0" '


            f'offsetTop="0" offsetBottom="0" connect="0" ignoreMargin="0"/></hh:paraPr>')








def patch_header(xml: str, thead_color: str = "#DAE3F3") -> str:


    """양식 header.xml 에 회의록 본문용 글자·문단·테두리 자원을 추가."""


    bf = ('<hh:borderFill id="%s" threeD="0" shadow="0" centerLine="NONE" '


          'breakCellSeparateLine="0"><hh:slash type="NONE" Crooked="0" isCounter="0"/>'


          '<hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'


          '<hh:leftBorder type="SOLID" width="0.12 mm" color="#000000"/>'


          '<hh:rightBorder type="SOLID" width="0.12 mm" color="#000000"/>'


          '<hh:topBorder type="SOLID" width="0.12 mm" color="#000000"/>'


          '<hh:bottomBorder type="SOLID" width="0.12 mm" color="#000000"/>'


          '<hh:diagonal type="SOLID" width="0.12 mm" color="#000000"/>'


          '<hc:fillBrush><hc:winBrush faceColor="%s" hatchColor="#000000" alpha="0"/>'


          '</hc:fillBrush></hh:borderFill>') % (BF_THEAD, thead_color)





    HUMAN, MALGUN = 6, 2          # fontfaces index : 휴먼명조 / 맑은 고딕


    cps = "".join([


        _charpr(CP_LABEL, 1200, HUMAN, bold=True, spacing=2),


        _charpr(CP_H2, 1300, HUMAN, bold=True),


        _charpr(CP_THEAD, 1000, MALGUN, bold=True),


        _charpr(CP_TBODY, 1000, MALGUN),


        _charpr(CP_CAPTION, 1100, HUMAN),


        _charpr(CP_TOPIC, 1500, HUMAN, bold=True),


        _charpr(CP_ATTEND, 1100, MALGUN),


        _charpr(CP_LABEL_S, 1200, HUMAN, bold=True, spacing=2),


    ])


    pps = "".join([


        _parapr(PP_H2, "JUSTIFY", left=1100, right=1000, intent=-2600, prev=700),


        _parapr(PP_B2, "JUSTIFY", left=2900, right=1000, intent=-1200, prev=400),


        _parapr(PP_B3, "JUSTIFY", left=4100, right=1000, intent=-1800, prev=300),


        _parapr(PP_CAPTION, "CENTER", left=500, right=500, prev=100, nxt=300),


        _parapr(PP_TCELL_C, "CENTER", spacing=140),


        _parapr(PP_TCELL_L, "JUSTIFY", left=100, right=100, spacing=140),


        _parapr(PP_ATTEND, "JUSTIFY", left=300, right=300, spacing=145, bfref="4"),


        _parapr(PP_TOPIC, "JUSTIFY", left=500, right=1000, intent=-2100, prev=1000),


        _parapr(PP_BLOCK, "CENTER", left=500, right=500, prev=300, nxt=300),


        _parapr(PP_NOTE, "JUSTIFY", left=2900, right=1000, intent=-1500, prev=500),


    ])





    def bump(tag, n, s):


        m = re.search(r'<hh:%s itemCnt="(\d+)"' % tag, s)


        return s[:m.start(1)] + str(int(m.group(1)) + n) + s[m.end(1):]





    xml = xml.replace("</hh:borderFills>", bf + "</hh:borderFills>")


    xml = xml.replace("</hh:charProperties>", cps + "</hh:charProperties>")


    xml = xml.replace("</hh:paraProperties>", pps + "</hh:paraProperties>")


    xml = bump("borderFills", 1, xml)


    xml = bump("charProperties", 8, xml)


    xml = bump("paraProperties", 10, xml)


    return xml








# --------------------------------------------------------------- 본문 조립 --


def frag(xml: str):


    """네임스페이스 선언을 붙여 파싱하고 자식 노드 리스트를 돌려준다."""


    wrapped = f"<w {NSDECL}>{xml}</w>"


    return list(etree.fromstring(wrapped.encode("utf-8")))








def cell_of(tbl, r, c):


    for tc in tbl.iter("{%s}tc" % HP):


        ca = tc.find("{%s}cellAddr" % HP)


        if ca.get("rowAddr") == str(r) and ca.get("colAddr") == str(c):


            return tc


    raise KeyError((r, c))








def set_cell_text(tbl, r, c, lines, ppr=None, cpr=None, pt=12, horzsize=None):


    """제목표 값 셀을 문단 리스트로 다시 채운다."""


    tc = cell_of(tbl, r, c)


    sub = tc.find("{%s}subList" % HP)


    first = sub[0]


    ppr = ppr or first.get("paraPrIDRef")


    cpr = cpr or first.find("{%s}run" % HP).get("charPrIDRef")


    width = horzsize or int(tc.find("{%s}cellSz" % HP).get("width")) - 400


    for p in list(sub):


        sub.remove(p)


    lines = lines if isinstance(lines, (list, tuple)) else [lines]


    if not lines:


        lines = [""]


    for line in lines:


        sub.extend(frag(para(ppr, runs_of(line, cpr, cpr), 0, pt, width)))


    return tc








def build_section0(tpl_xml: bytes, spec: dict, images_dir: Path | None):


    root = etree.fromstring(tpl_xml)


    tbl = root.iter("{%s}tbl" % HP).__next__()





    # --- 제목표 ---------------------------------------------------------


    set_cell_text(tbl, 2, 1, spec.get("title", ""), PP_TITLE_VAL, CP_TITLE_VAL, 12)


    set_cell_text(tbl, 3, 1, spec.get("datetime", ""), PP_HDR_VAL, CP_HDR_VAL, 12)


    set_cell_text(tbl, 3, 3, spec.get("author", ""), PP_HDR_VAL, CP_HDR_NAME, 11)


    set_cell_text(tbl, 4, 1, spec.get("location", ""), PP_TITLE_VAL, CP_HDR_VAL, 12)


    set_cell_text(tbl, 4, 3, spec.get("manager", ""), PP_HDR_VAL, CP_HDR_NAME, 11)





    att = spec.get("attendees") or []


    att = [att] if isinstance(att, str) else list(att)


    atc = set_cell_text(tbl, 5, 1, att or [""], PP_ATTEND, CP_ATTEND, 11)


    aw = int(atc.find("{%s}cellSz" % HP).get("width")) - 900


    ah = sum(nlines(x, 11, aw) for x in (att or [""])) * 1750 + 600


    atc.find("{%s}cellSz" % HP).set("height", str(max(7252, ah)))





    # --- 본문 -----------------------------------------------------------


    doc = Doc(images_dir)


    sections = spec.get("sections") or []


    n = 0


    for sec in sections:


        if sec.get("topic"):


            doc.topic(sec["topic"])


        if sec.get("heading"):


            n += 1


            doc.heading(sec.get("number") or n, sec["heading"])


        doc._auto_sec = 0


        doc.render(sec.get("blocks"))


    for b in spec.get("blocks") or []:                 # sections 없이 쓰는 경우


        doc.render([b])





    body = cell_of(tbl, 7, 0)


    sub = body.find("{%s}subList" % HP)


    for p in list(sub):


        sub.remove(p)


    if not doc.parts:


        doc.parts.append(para(PP_B1, f'<hp:run charPrIDRef="{CP_BODY}"><hp:t></hp:t>'


                              f'</hp:run>', 1100, 12))


    sub.extend(frag("".join(doc.parts)))





    # --- 높이 보정 ------------------------------------------------------


    bh = max(20000, doc.height + 2000)


    body.find("{%s}cellSz" % HP).set("height", str(bh))


    total = 0


    for tr in tbl.findall("{%s}tr" % HP):


        tc = tr.find("{%s}tc" % HP)


        total += int(tc.find("{%s}cellSz" % HP).get("height"))


    tbl.find("{%s}sz" % HP).set("height", str(total))





    out = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


    return out, doc








# ------------------------------------------------------------------ 저장 ----


def preview_text(spec, doc) -> str:


    L = ["<회의록>", f"<제 목><{spec.get('title','')}>",


         f"<일 시><{spec.get('datetime','')}><작성자><{spec.get('author','')}>",


         f"<장 소><{spec.get('location','')}><관리자><{spec.get('manager','')}>",


         "<참석자><" + " ".join(spec.get("attendees") or []) + ">",


         "< ■ 회의 내용>"]


    L += ["<" + l.strip() + ">" for l in doc.plain[:60]]


    return "\n".join(L)








def write_hwpx(spec, out_path: Path, images_dir: Path | None, thead_color="#DAE3F3"):


    zin = zipfile.ZipFile(TEMPLATE)


    infos = zin.infolist()


    data = {i.filename: zin.read(i.filename) for i in infos}


    ctype = {i.filename: i.compress_type for i in infos}


    order = [i.filename for i in infos]


    zin.close()





    sec, doc = build_section0(data["Contents/section0.xml"], spec, images_dir)


    data["Contents/section0.xml"] = sec


    data["Contents/header.xml"] = patch_header(


        data["Contents/header.xml"].decode("utf-8"), thead_color).encode("utf-8")


    data["Preview/PrvText.txt"] = preview_text(spec, doc).encode("utf-8")





    # 그림 등록


    items = []


    for fname, raw, mt in doc.images:


        path = "BinData/" + fname


        data[path] = raw


        ctype[path] = zipfile.ZIP_DEFLATED


        order.insert(order.index("Contents/section0.xml"), path)


        iid = fname.rsplit(".", 1)[0]


        items.append(f'<opf:item id="{iid}" href="{path}" media-type="{mt}" '


                     f'isEmbeded="1"/>')


    hpf = data["Contents/content.hpf"].decode("utf-8")


    hpf = re.sub(r"<opf:title>.*?</opf:title>",


                 "<opf:title>" + esc(spec.get("title", "회의록")) + "</opf:title>",


                 hpf, flags=re.S)


    if items:


        hpf = hpf.replace('<opf:item id="section0"', "".join(items)


                          + '<opf:item id="section0"')


    data["Contents/content.hpf"] = hpf.encode("utf-8")





    out_path.parent.mkdir(parents=True, exist_ok=True)


    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:


        for n in order:


            z.writestr(zipfile.ZipInfo(n), data[n], compress_type=ctype[n])


    return doc








# ----------------------------------------------------------------- 검증 ----


def verify(out_path: Path):


    z = zipfile.ZipFile(out_path)


    bad = z.testzip()


    hdr = z.read("Contents/header.xml").decode("utf-8")


    sec = z.read("Contents/section0.xml").decode("utf-8")


    etree.fromstring(z.read("Contents/section0.xml"))


    etree.fromstring(z.read("Contents/header.xml"))





    def defined(tag):


        return set(re.findall(r'<hh:%s id="(\d+)"' % tag, hdr))


    cp, pp, bf = defined("charPr"), defined("paraPr"), defined("borderFill")


    used_cp = set(re.findall(r'charPrIDRef="(\d+)"', sec))


    used_pp = set(re.findall(r'paraPrIDRef="(\d+)"', sec))


    used_bf = set(re.findall(r'borderFillIDRef="(\d+)"', sec))


    missing = sorted(


        [f"charPr:{x}" for x in used_cp - cp]


        + [f"paraPr:{x}" for x in used_pp - pp]


        + [f"borderFill:{x}" for x in used_bf - bf])


    bins = {n for n in z.namelist() if n.startswith("BinData/")}


    hpf = z.read("Contents/content.hpf").decode("utf-8")


    refs = set(re.findall(r'binaryItemIDRef="([^"]+)"', sec))


    declared = set(re.findall(r'<opf:item id="(image[^"]*)"', hpf))


    return {


        "output": str(out_path),


        "size_bytes": out_path.stat().st_size,


        "zip_ok": bad is None,


        "missing_style_ids": missing,


        "images_in_zip": sorted(bins),


        "image_refs_resolved": sorted(refs - declared) == [],


        "PASS": bad is None and not missing and sorted(refs - declared) == [],


    }








# --------------------------------------------------------------- 더미 예시 --


def default_spec():


    return {


        "meta": {"output": "회의록_예시.hwpx"},


        "title": "○○○ 추진방향 검토를 위한 간담회",


        "datetime": "2026년 9월 21일 14시",


        "author": "홍길동",


        "location": "○○관 ○○○호",


        "manager": "김철수",


        "attendees": [


            "(○○본부) 팀장 김철수, 이영희, 박민수",


            "주무관 정수민, 최지훈, 강하늘, 임재현, 홍길동, 표은지, 천유진, 구본영",


        ],


        "sections": [


            {"heading": "회의 목적", "blocks": [


                {"type": "bullet", "text": "○○○ 사업 추진에 앞서 현황을 공유하고 "


                                           "추진방향 및 요구사항에 반영할 시사점 논의"}]},


            {"heading": "주요 논의 사항", "blocks": [


                {"type": "subheading", "text": "현황 및 문제점"},


                {"type": "bullet", "label": "통합 관리 체계 부재",


                 "text": "시스템별로 상이한 관리 기준을 적용하고 있어 데이터 간 중복 및 "


                         "불일치 현상이 발생하며, 전사적 차원의 표준화가 필요함"},


                {"type": "subbullet", "text": "자원 보유 및 예약 창구 현황은 다음과 같음"},


                {"type": "table",


                 "headers": ["구분", "주요 업무", "보유 수량", "현행 창구"],


                 "widths": [8, 20, 8, 9],


                 "align": ["center", "left", "center", "center"],


                 "rows": [


                     ["교육시설", "강의실 · 실습실",


                      "0,000개", "00,000개"],


                     ["연구시설", "홈페이지통합시스템·대표홈페이지 등 000실",


                      "0,000개", "00,000개"]]},


                {"type": "note", "text": "현행 창구는 중복 포함 기준"},


                {"type": "subheading", "text": "검토사항"},


                {"type": "bullet", "text": "1차년도 전수 진단 및 표본 진단 대상을 "


                                           "사업 착수 전 명확히 구분 필요"},


                {"type": "subsub", "text": "품질 지표 및 점검 프로세스 확립 방안 병행 검토"}]},


            {"heading": "추후 일정", "blocks": [


                {"type": "bullet", "text": "사례조사 결과를 반영하여 제안요청서 요구사항 보완"},


                {"type": "bullet", "text": "우선 대상 자원 목록 확정 및 후속 간담회 실시"}]},


        ],


    }








# ------------------------------------------------------- 텍스트 개요 파서 ---


HEAD_KEYS = {


    "제목": "title", "제 목": "title", "회의명": "title", "회의제목": "title",


    "일시": "datetime", "일 시": "datetime", "회의일시": "datetime",


    "작성자": "author", "작 성 자": "author",


    "장소": "location", "장 소": "location",


    "관리자": "manager", "관 리 자": "manager",


    "참석자": "attendees", "참 석 자": "attendees",


    "출력": "output", "파일명": "output",


}





OUTLINE_TEMPLATE = """\


# ==========================================================================


#  회의록 개요 — 이 파일을 채워서 저장한 뒤


#    · Claude Code 에서  /회의록 이파일.txt   또는


#    · python build_minutes.py 이파일.txt --pdf --open


#  으로 실행하면 회의록 HWPX 가 만들어집니다.


#


#  · '#' 으로 시작하는 줄은 무시됩니다. 설명은 지우지 않아도 됩니다.


#  · 비워 둔 칸은 defaults.json 의 기본값으로 채워집니다.


#  · 파일명은 «제목_회의록_날짜_작성자.hwpx» 로 자동 생성됩니다.


# ==========================================================================





제목:


일시:


작성자:


장소:


관리자:


# 참석자는 줄마다 하나씩, 한 줄 40자 안쪽에서 끊어 주세요.


참석자:


참석자:





# ---- 본문 ----------------------------------------------------------------


#  1.      절 표제        (번호는 적은 대로 나갑니다)


#  가.     소제목         (절 안이 두 갈래 이상일 때만)


#  ◦       글머리         ◦ (라벨) 본문   → (라벨) 은 자동으로 굵게


#    -     하위 글머리


#      ○   세부 글머리


#  ※       단서·근거


#  □       대주제         (절 위에 큰 제목이 필요할 때)


#  **굵게** 로 강조할 수 있습니다.


# --------------------------------------------------------------------------





1. 회의 목적


◦





2. 주요 논의 사항


가.


◦ ()


  -


    ○


  ※





# ---- 표 (첫 줄이 머리행, 칸은 | 로 구분) ---------------------------------


# [표] 표 제목


# 구분 | 주요 업무 | 보유 수량


# 교육시설 | 강의실 · 실습실 | 0,000개


# 연구시설 | 홈페이지통합시스템 등 000실 | 0,000개


# =합계 | 000실 | 0,000개


# [끝]


#   · 열 폭과 정렬은 내용에 맞춰 자동 조정됩니다.


#   · 행 맨 앞에 '=' 를 붙이면 합계행(음영+굵게)이 됩니다.


#   · 칸에 '^' 를 쓰면 위 칸과 세로로 병합됩니다.





# ---- 그림 (한 줄에 1~2장 권장) -------------------------------------------


# [그림] 화면1.png | 화면2.png


# [캡션] 예약 화면 | 승인 화면





3. 추후 일정


◦


"""








def parse_outline(text: str) -> dict:


    """사람이 손으로 쓴 개요 텍스트를 콘텐츠 스펙으로 변환.





    제목표는 `키: 값` 줄, 본문은 완성된 회의록처럼 글머리 기호를 그대로 적는다.


      1. / 2.  절 표제        가. / 나.  소제목        □  대주제


      ◦ (라벨) 본문           - 하위        ○ 세부        ※ 단서


      [표] 캡션 … [끝]        [그림] a.png | b.png / [캡션] …


    """


    spec: dict = {"attendees": [], "sections": []}


    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


    cur: dict | None = None


    blocks: list = []


    table: dict | None = None


    auto_no = 0





    def flush_section():


        nonlocal cur, blocks


        if cur is not None:


            cur["blocks"] = blocks


            spec["sections"].append(cur)


        cur, blocks = None, []





    def ensure_section():


        nonlocal cur, blocks, auto_no


        if cur is None:


            auto_no += 1


            cur = {"heading": "회의 내용", "number": auto_no}


            blocks = []





    for raw in lines:


        line = raw.rstrip()


        s = line.strip()





        # --- 표 블록 안 --------------------------------------------------


        if table is not None:


            if s in ("[끝]", "[/표]", "[표끝]"):


                cells = table["cells"]


                if cells:


                    hdr, body = cells[0], cells[1:]


                    shade = [i for i, r in enumerate(body) if r and r[0].startswith("=")]


                    body = [[c[1:].strip() if j == 0 and c.startswith("=") else c


                             for j, c in enumerate(r)] for r in body]


                    ensure_section()


                    blocks.append({"type": "table", "headers": hdr, "rows": body,


                                   "shade_rows": shade,


                                   "caption": table["caption"] or None})


                table = None


                continue


            if s:


                table["cells"].append([c.strip() for c in s.split("|")])


            continue





        if not s or s.startswith("#"):          # 빈 줄 · # 주석줄 무시


            continue





        # --- 구분선 ------------------------------------------------------


        if set(s) <= set("-=—_") and len(s) >= 3:


            continue





        # --- 제목표 (키: 값) ----------------------------------------------


        m = re.match(r"^\[?\s*([가-힣 ]{2,6})\s*\]?\s*[:：]\s*(.*)$", s)


        if m and m.group(1).replace(" ", "") in {k.replace(" ", "") for k in HEAD_KEYS}:


            key = next(v for k, v in HEAD_KEYS.items()


                       if k.replace(" ", "") == m.group(1).replace(" ", ""))


            val = m.group(2).strip()


            if key == "attendees":


                if val:


                    spec["attendees"].append(val)


            elif key == "output":


                spec.setdefault("meta", {})["output"] = val


            else:


                spec[key] = val


            continue





        # --- 표/그림 시작 -------------------------------------------------


        m = re.match(r"^\[\s*표\s*\](.*)$", s)


        if m:


            table = {"caption": m.group(1).strip(), "cells": []}


            continue


        m = re.match(r"^\[\s*그림\s*\](.*)$", s)


        if m:


            files = [x.strip() for x in m.group(1).split("|") if x.strip()]


            ensure_section()


            blocks.append({"type": "image", "files": files, "captions": []})


            continue


        m = re.match(r"^\[\s*캡션\s*\](.*)$", s)


        if m:


            caps = [x.strip() for x in m.group(1).split("|")]


            if blocks and blocks[-1].get("type") == "image":


                blocks[-1]["captions"] = caps


            else:


                ensure_section()


                blocks.append({"type": "caption", "text": " ".join(caps)})


            continue





        # --- 대주제 □ -----------------------------------------------------


        m = re.match(r"^[□■]\s*(.+)$", s)


        if m:


            flush_section()


            auto_no += 1


            cur = {"heading": None, "topic": m.group(1).strip(), "number": auto_no}


            blocks = []


            auto_no -= 1


            continue





        # --- 절 표제 (1. …) -----------------------------------------------


        m = re.match(r"^(\d{1,2})\s*[.)]\s*(.+)$", s)


        if m:


            flush_section()


            auto_no += 1


            cur = {"heading": m.group(2).strip(), "number": int(m.group(1))}


            blocks = []


            continue





        # --- 소제목 (가. …) -----------------------------------------------


        m = re.match(r"^([가-하])\s*[.)]\s*(.+)$", s)


        if m:


            ensure_section()


            blocks.append({"type": "subheading", "marker": m.group(1) + ".",


                           "text": m.group(2).strip()})


            continue





        # --- 글머리 -------------------------------------------------------


        m = re.match(r"^([◦ㅇ○o•◇·※⁃–—-]|\*)\s*(.*)$", s)


        if m:


            mark, body = m.group(1), m.group(2).strip()


            if not body:


                continue


            ensure_section()


            indent = len(line) - len(line.lstrip())


            if mark == "※":


                blocks.append({"type": "note", "text": body})


            elif mark in ("-", "–", "—", "⁃", "*"):


                blocks.append({"type": "subbullet", "text": body})


            elif mark in ("○", "◇", "o"):


                blocks.append({"type": "subsub", "text": body})


            else:                                   # ◦ ㅇ • ·


                kind = "subsub" if indent >= 6 else ("subbullet" if indent >= 4


                                                    else "bullet")


                blocks.append({"type": kind, "text": body})


            continue





        # --- 기호 없는 줄 -> 들여쓰기로 판단 ------------------------------


        ensure_section()


        indent = len(line) - len(line.lstrip())


        kind = "subsub" if indent >= 6 else ("subbullet" if indent >= 3 else "bullet")


        blocks.append({"type": kind, "text": s})





    flush_section()


    for sec in spec["sections"]:


        if sec.get("heading") is None:


            sec.pop("heading", None)


            sec.pop("number", None)


    return spec








def apply_defaults(spec: dict, defaults: dict) -> dict:


    """defaults.json 의 상용 값(작성자·관리자·장소·상시 참석자)을 비어 있는 칸에만 채운다."""


    for k in ("author", "manager", "location", "datetime", "title"):


        if not str(spec.get(k) or "").strip() and defaults.get(k):


            spec[k] = defaults[k]


    if not [a for a in (spec.get("attendees") or []) if str(a).strip()]:


        if defaults.get("attendees"):


            spec["attendees"] = list(defaults["attendees"])


    return spec








def auto_output_name(spec: dict) -> str:


    import datetime as _dt


    title = re.sub(r'[\\/:*?"<>|]', "", str(spec.get("title") or "회의록")).strip()


    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", str(spec.get("datetime") or ""))


    ymd = (f"{int(m.group(1)):04d}{int(m.group(2)):02d}{int(m.group(3)):02d}"


           if m else _dt.date.today().strftime("%Y%m%d"))


    author = str(spec.get("author") or "").strip()


    tail = f"_{author}" if author else ""


    return f"{title}_회의록_{ymd}{tail}.hwpx"








SCHEMA = r"""


{


  "meta":      { "output": "출력파일.hwpx" },


  "title":     "회의 제목(간담회 명칭)",


  "datetime":  "2026년 9월 21일 14시",


  "author":    "작성자",


  "location":  "장소",


  "manager":   "관리자",


  "attendees": ["(부서) 팀장 …", "주무관 …"],          // 줄 단위 배열


  "sections": [


    { "heading": "절 제목",            // → "1. 절 제목" (번호 자동)


      "number": 3,                     // (선택) 번호 강제 지정


      "topic":  "대주제",              // (선택) → "□ 대주제" 를 절 위에 출력


      "blocks": [


        { "type": "bullet",     "label": "라벨", "text": "본문" },   // ◦ (라벨) 본문


        { "type": "subbullet",  "text": "하위 항목" },               // - 하위 항목


        { "type": "subsub",     "text": "세부 항목" },               // ○ 세부 항목


        { "type": "subheading", "text": "소제목" },                  // 가. 소제목(자동 가나다)


        { "type": "subheading", "marker": "나.", "text": "소제목" },


        { "type": "note",       "text": "단서" },                    // ※ 단서


        { "type": "spacer" },


        { "type": "table",


          "headers": ["구분", "내용"],


          "widths":  [10, 34],                 // 상대 비율


          "align":   ["center", "left"],


          "rows":    [["가", "나"], ["^", "다"]],   // "^" = 위 셀과 세로 병합


          "total_row": true,                   // 마지막 행을 합계행(음영+굵게)으로


          "shade_rows": [0],                   // 음영 처리할 데이터 행(0-base)


          "caption": "표 제목" },


        { "type": "image",


          "files":    ["a.png", "b.png"],      // 한 줄에 나란히 배치


          "captions": ["교육 계획", "유지보수 계획"],


          "max_height": 22000 }


      ] }


  ]


}


본문 어디서든 `**굵게**` 사용 가능. text 앞의 `(라벨)` 은 자동으로 굵게 처리된다.


"""








DEFAULTS_PATH = HERE.parent / "defaults.json"








def read_text_any(path: Path) -> str:


    raw = path.read_bytes()


    for enc in ("utf-8-sig", "utf-8", "cp949", "utf-16"):


        try:


            return raw.decode(enc)


        except UnicodeDecodeError:


            continue


    return raw.decode("utf-8", "replace")








def open_in_hangul(path: Path):


    try:


        import subprocess


        subprocess.Popen(["cmd", "/c", "start", "", str(path.resolve())], shell=False)


    except Exception as e:                                     # pragma: no cover


        print(f"[WARN] 한글로 열지 못했습니다: {e}")








# ------------------------------------------------------------------ main ----


def main():


    ap = argparse.ArgumentParser(


        description="회의록 HWPX 생성기 — 텍스트 개요(-t) 또는 콘텐츠 JSON(-c) 으로 만든다")


    ap.add_argument("input", nargs="?",


                    help="입력 파일. .txt/.md 는 개요, .json 은 콘텐츠 스펙으로 처리")


    ap.add_argument("-t", "--outline", help="텍스트 개요 경로")


    ap.add_argument("-c", "--content", help="콘텐츠 JSON 경로")


    ap.add_argument("-o", "--output", help="출력 hwpx 경로(생략 시 자동 이름)")


    ap.add_argument("--images-dir", help="그림 상대경로 기준 디렉터리")


    ap.add_argument("--thead-color", default="#DAE3F3", help="표 머리행 배경색")


    ap.add_argument("--open", action="store_true", help="생성 후 한글로 열기")


    ap.add_argument("--pdf", action="store_true", help="생성 후 PDF 도 함께 만들기")


    ap.add_argument("--no-defaults", action="store_true", help="defaults.json 무시")


    ap.add_argument("--schema", action="store_true", help="콘텐츠 JSON 스키마 출력")


    ap.add_argument("--template", action="store_true", help="개요 작성 서식 출력")


    ap.add_argument("--selftest", action="store_true", help="더미 콘텐츠로 빌드 검증")


    a = ap.parse_args()





    if a.schema:


        print(SCHEMA)


        return


    if a.template:


        print(OUTLINE_TEMPLATE)


        return





    src = a.content or a.outline or a.input


    is_json = bool(a.content) or (src and str(src).lower().endswith(".json"))





    if src:


        p = Path(src)


        if not p.exists():


            raise SystemExit(f"[ERROR] 입력 파일 없음: {p}")


        spec = (json.loads(read_text_any(p)) if is_json


                else parse_outline(read_text_any(p)))


        images_dir = Path(a.images_dir) if a.images_dir else p.resolve().parent


    else:


        spec = default_spec()


        images_dir = Path(a.images_dir) if a.images_dir else None





    if not a.no_defaults and DEFAULTS_PATH.exists():


        try:


            spec = apply_defaults(spec, json.loads(read_text_any(DEFAULTS_PATH)))


        except Exception as e:


            print(f"[WARN] defaults.json 을 읽지 못했습니다: {e}")





    if not TEMPLATE.exists():


        raise SystemExit(f"[ERROR] 템플릿 없음: {TEMPLATE}")





    out = Path(a.output or (spec.get("meta") or {}).get("output")


               or ((images_dir or Path(".")) / auto_output_name(spec)))


    write_hwpx(spec, out, images_dir, a.thead_color)





    report = verify(out)


    report["sections"] = [s.get("heading") or s.get("topic") or ""


                          for s in (spec.get("sections") or [])]


    missing = [ko for ko, k in (("일시", "datetime"), ("작성자", "author"),


                                ("장소", "location"), ("관리자", "manager"))


               if not str(spec.get(k) or "").strip()]


    if not [x for x in (spec.get("attendees") or []) if str(x).strip()]:


        missing.append("참석자")


    report["empty_fields"] = missing





    if a.pdf:


        pdf = out.with_suffix(".pdf")


        try:


            sys.path.insert(0, str(HERE))


            import subprocess


            subprocess.run([sys.executable, str(HERE / "hwp2pdf.py"),


                            str(out), str(pdf)], check=False)


            report["pdf"] = str(pdf) if pdf.exists() else None


        except Exception as e:


            report["pdf_error"] = str(e)


    if a.open:


        open_in_hangul(out)





    print(json.dumps(report, ensure_ascii=False, indent=2))








if __name__ == "__main__":


    main()


