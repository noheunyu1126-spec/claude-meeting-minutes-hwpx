# -*- coding: utf-8 -*-
"""생성한 HWPX 를 한컴오피스 한글(COM)로 열어 PDF 로 저장 — 육안 검증용.

    python hwp2pdf.py 결과.hwpx 결과.pdf

한글이 설치돼 있어야 한다(HWPFrame.HwpObject). 창은 띄우지 않는다.
PDF 를 이미지로 확인하려면:
    python -c "import fitz,sys;d=fitz.open(sys.argv[1]);[p.get_pixmap(dpi=120).save(f'pg{i+1}.png') for i,p in enumerate(d)]" 결과.pdf
"""
import os
import sys


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    src, dst = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    import win32com.client as win32
    hwp = win32.gencache.EnsureDispatch("HWPFrame.HwpObject")
    try:
        hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
    except Exception:
        pass                                     # 보안 모듈 없이도 대개 열린다
    try:
        hwp.XHwpWindows.Item(0).Visible = False
    except Exception:
        pass
    if not hwp.Open(src, "HWPX", "forceopen:true"):
        raise SystemExit(f"[ERROR] 열기 실패: {src}")
    act = hwp.CreateAction("FileSaveAsPdf")
    pset = act.CreateSet()
    act.GetDefault(pset)
    pset.SetItem("FileName", dst)
    pset.SetItem("Format", "PDF")
    pset.SetItem("Attributes", 0)
    ok = act.Execute(pset)
    hwp.Clear(1)
    hwp.Quit()
    print(f"pdf saved: {bool(ok)} exists={os.path.exists(dst)} -> {dst}")


if __name__ == "__main__":
    main()
