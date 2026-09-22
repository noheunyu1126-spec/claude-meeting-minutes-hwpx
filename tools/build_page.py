# -*- coding: utf-8 -*-
"""README.md -> index.html (GitHub Pages 용)

GitHub Pages(Jekyll)는 ```mermaid 블록을 그려 주지 않으므로, README 를 미리 HTML 로
변환하고 mermaid.js 를 붙인 한 장 페이지를 만든다.

    python tools/build_page.py
"""
import html
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import markdown

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "README.md"
DST = ROOT / "index.html"

text = SRC.read_text(encoding="utf-8")

# --- mermaid 블록을 자리표시자로 빼둔다 --------------------------------
diagrams = []


def stash(m):
    diagrams.append(m.group(1))
    return f"\n\nMERMAIDPLACEHOLDER{len(diagrams) - 1}\n\n"


text = re.sub(r"```mermaid\n(.*?)```", stash, text, flags=re.S)

body = markdown.markdown(
    text,
    extensions=["tables", "fenced_code", "toc", "sane_lists", "attr_list"],
    extension_configs={"toc": {"permalink": False}},
)

for i, d in enumerate(diagrams):
    body = body.replace(
        f"<p>MERMAIDPLACEHOLDER{i}</p>",
        f'<div class="mermaid-wrap"><pre class="mermaid">{html.escape(d)}</pre></div>')

TITLE = "회의록 작성 스킬 · /회의록"
DESC = ("발표자료 PDF 하나로 「회의록」 양식 HWPX 문서를 만드는 Claude Code 스킬 "
        "— 설치·사용법 한 장 설명서")

PAGE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<meta name="description" content="__DESC__">
<style>
:root{
  --bg:#f5f6f8; --panel:#fff; --panel-2:#f8f9fb; --ink:#191c21; --ink-2:#4e5663;
  --ink-3:#8b93a1; --line:#e1e5eb; --line-2:#eef1f5;
  --accent:#2f5597; --accent-soft:#dbe4f5;
  --warn:#8a5a00; --warn-bg:#fff7e6;
  --mono:"Consolas","D2Coding","Malgun Gothic",ui-monospace,monospace;
  --sans:"Malgun Gothic","Apple SD Gothic Neo",system-ui,-apple-system,sans-serif;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#15171b; --panel:#1d2025; --panel-2:#23262c; --ink:#e9ebee; --ink-2:#a9b1bd;
  --ink-3:#7b8494; --line:#32373e; --line-2:#292d33;
  --accent:#7aa5e6; --accent-soft:#273349; --warn:#e2b45f; --warn-bg:#332915;
}}
:root[data-theme="dark"]{
  --bg:#15171b; --panel:#1d2025; --panel-2:#23262c; --ink:#e9ebee; --ink-2:#a9b1bd;
  --ink-3:#7b8494; --line:#32373e; --line-2:#292d33;
  --accent:#7aa5e6; --accent-soft:#273349; --warn:#e2b45f; --warn-bg:#332915;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
  font-size:15px;line-height:1.7;-webkit-font-smoothing:antialiased}
.shell{max-width:940px;margin:0 auto;padding:36px 16px 80px}
.themebtn{position:fixed;top:12px;right:14px;z-index:9;border:1px solid var(--line);
  background:var(--panel);color:var(--ink);border-radius:99px;width:34px;height:34px;
  cursor:pointer;font-size:14px;line-height:1;box-shadow:0 1px 4px rgba(0,0,0,.08)}

h1{font-size:clamp(25px,5vw,36px);line-height:1.22;letter-spacing:-.02em;
  margin:0 0 18px;padding-bottom:0;border:0}
h2{font-size:21px;letter-spacing:-.01em;margin:44px 0 12px;padding-bottom:8px;
  border-bottom:1px solid var(--line)}
h3{font-size:16px;margin:26px 0 8px}
p{margin:12px 0;color:var(--ink-2)}
p strong,li strong,td strong{color:var(--ink);font-weight:700}
hr{border:0;border-top:1px solid var(--line);margin:36px 0}
a{color:var(--accent);text-decoration-thickness:1px;text-underline-offset:2px}

code{font-family:var(--mono);font-size:.875em;background:var(--panel-2);
  border:1px solid var(--line-2);border-radius:4px;padding:1px 5px;color:var(--ink)}
pre{background:var(--panel-2);border:1px solid var(--line);border-radius:8px;
  padding:14px 16px;overflow-x:auto;margin:14px 0;
  font-family:var(--mono);font-size:12.5px;line-height:1.62}
pre code{background:none;border:0;padding:0;font-size:inherit}

table{width:100%;border-collapse:collapse;font-size:14px;margin:14px 0;
  background:var(--panel);border:1px solid var(--line);border-radius:8px;
  overflow:hidden;display:table}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line-2);
  vertical-align:top}
th{font-size:12px;color:var(--ink-3);font-weight:700;letter-spacing:.04em;
  background:var(--panel-2);border-bottom:1px solid var(--line);white-space:nowrap}
tbody tr:last-child td{border-bottom:0}
td code{white-space:nowrap}

ul,ol{margin:12px 0;padding-left:22px;color:var(--ink-2)}
li{margin:5px 0}
blockquote{margin:16px 0;padding:12px 16px;background:var(--warn-bg);
  border:1px solid color-mix(in srgb,var(--warn) 35%,transparent);
  border-radius:8px;color:var(--ink-2)}
blockquote p{margin:4px 0}
blockquote strong{color:var(--warn)}

details{margin:14px 0;border:1px solid var(--line);border-radius:8px;
  background:var(--panel);overflow:hidden}
details>summary{cursor:pointer;padding:11px 15px;font-size:13.5px;color:var(--ink-2);
  background:var(--panel-2);font-weight:600}
details>summary:hover{color:var(--ink)}
details>*:not(summary){margin-left:15px;margin-right:15px}

.mermaid-wrap{background:var(--panel);border:1px solid var(--line);border-radius:10px;
  padding:18px 14px;margin:16px 0;overflow-x:auto;text-align:center}
pre.mermaid{background:none;border:0;padding:0;margin:0;text-align:center;
  font-family:var(--sans);font-size:14px}
.mermaid-wrap svg{max-width:100%;height:auto}

footer{margin-top:56px;padding-top:18px;border-top:1px solid var(--line);
  color:var(--ink-3);font-size:12.5px}
@media (max-width:640px){
  pre{font-size:11.5px}
  table{font-size:13px}
  th,td{padding:7px 9px}
}
</style>
</head>
<body>
<button class="themebtn" id="theme" title="밝게/어둡게" aria-label="테마 전환">◐</button>
<div class="shell">
__BODY__
<footer>
  회의록 작성 스킬 · 결과 확인은 한컴오피스 한글에서 합니다.
  이 문서의 회의 내용·이름·기관·수치는 모두 가상 예시입니다.
</footer>
</div>

<script type="module">
import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
const dark = () => {
  const t = document.documentElement.getAttribute("data-theme");
  if (t) return t === "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
};
const render = () => {
  document.querySelectorAll("pre.mermaid").forEach(el => {
    if (el.dataset.src === undefined) el.dataset.src = el.textContent;
    el.removeAttribute("data-processed");
    el.innerHTML = el.dataset.src;
  });
  mermaid.initialize({
    startOnLoad: false,
    theme: dark() ? "dark" : "default",
    fontFamily: '"Malgun Gothic","Apple SD Gothic Neo",system-ui,sans-serif',
    flowchart: { htmlLabels: true, curve: "basis" }
  });
  mermaid.run({ querySelector: "pre.mermaid" });
};
render();
window.__rerenderMermaid = render;
</script>
<script>
(function(){
  var root = document.documentElement, btn = document.getElementById("theme");
  try{ var s = localStorage.getItem("mn-doc-theme"); if(s) root.setAttribute("data-theme", s); }catch(e){}
  btn.addEventListener("click", function(){
    var cur = root.getAttribute("data-theme");
    var next = cur === "dark" ? "light" : cur === "light" ? "dark" : "light";
    root.setAttribute("data-theme", next);
    try{ localStorage.setItem("mn-doc-theme", next); }catch(e){}
    if (window.__rerenderMermaid) window.__rerenderMermaid();
  });
})();
</script>
</body>
</html>
"""

out = (PAGE.replace("__TITLE__", html.escape(TITLE))
           .replace("__DESC__", html.escape(DESC))
           .replace("__BODY__", body))
DST.write_text(out, encoding="utf-8")
print(f"{DST.name} 생성 — {len(out):,} bytes, mermaid 도식 {len(diagrams)}개")
