#!/usr/bin/env python3
"""Usage: python3 render.py data.json OUTDIR
{fact_id} 치환 후 1080x1350 JPEG 캐러셀 + caption.txt + manifest.json 생성.
디자인 v2: 표지 훅(큰 헤드라인·KPI 칩·스와이프 유도), 지표 타일+등락 막대, 번호 카드, 진행 바,
핵심 요소는 중앙 1080x1080 안전 영역(위아래 135px 제외) 안에 배치 — 1:1로 잘려도 내용 보존."""
import json, sys, html, os, re
from playwright.sync_api import sync_playwright

data = json.load(open(sys.argv[1], encoding="utf-8"))
FACTS = {f["id"]: f["value"] for f in data.get("facts", [])}
def fill(x):
    if isinstance(x, str):
        return re.sub(r"\{([a-z0-9_]+)\}", lambda m: FACTS[m.group(1)], x)
    if isinstance(x, list): return [fill(v) for v in x]
    if isinstance(x, dict): return {k: (v if k == "facts" else fill(v)) for k, v in x.items()}
    return x
data = fill(data)
out = sys.argv[2]; os.makedirs(out, exist_ok=True)
E = html.escape

def tone(s):
    s = str(s).strip()
    return "up" if s[:1] in "+▲" else "dn" if s[:1] in "-−▼" else "fl"

def arrow(s):
    return {"up": "▲", "dn": "▼", "fl": "■"}[tone(s)]

def colorize(text):
    """텍스트 속 +x% / -x% 같은 등락 표기에 색을 입힌다 (값은 그대로)."""
    t = E(text)
    return re.sub(r"(?<![\w.])([+\-−][\d.,]+(?:%|bp|원|만|조)?)",
                  lambda m: f'<b class="{tone(m.group(1))}">{m.group(1)}</b>', t)

def pct(s):
    m = re.match(r"\s*([+\-−]?\d+(?:\.\d+)?)\s*%\s*$", str(s).replace("−", "-"))
    return abs(float(m.group(1))) if m else None

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#0b1220;--card:#131d31;--card2:#18243c;--line:#24324f;--tx:#f2f5fa;--mut:#93a3bd;--dim:#5f7090;
 --acc:#4d9bff;--hl:#ffd24a;--up:#ff5b61;--dn:#4d9bff}
body{width:1080px;height:1350px;background:var(--bg);color:var(--tx);overflow:hidden;position:relative;
 font-family:'Noto Sans CJK KR','Noto Sans KR',sans-serif;word-break:keep-all}
.bgglow{position:absolute;inset:0;background:radial-gradient(900px 600px at 85% -10%,rgba(77,155,255,.22),transparent 60%),
 radial-gradient(700px 500px at -10% 110%,rgba(255,210,74,.08),transparent 60%)}
.top{position:absolute;top:44px;left:72px;right:72px;height:56px;display:flex;align-items:center;justify-content:space-between;
 color:var(--mut);font-size:25px;font-weight:600}
.brand{display:flex;align-items:center;gap:14px;color:var(--tx)}
.brand svg{width:44px;height:44px}
.safe{position:absolute;left:72px;right:72px;top:150px;bottom:200px;display:flex;flex-direction:column}
.tag{align-self:flex-start;font-size:26px;font-weight:800;letter-spacing:.5px;padding:10px 22px;border-radius:999px;
 background:rgba(77,155,255,.14);color:#9cc8ff;border:1.5px solid rgba(77,155,255,.35)}
h1{white-space:pre-line;font-size:76px;line-height:1.16;font-weight:900;letter-spacing:-2px;margin-top:26px}
h1 em{font-style:normal;color:var(--hl)}
.sub{font-size:29px;color:var(--mut);margin-top:18px;line-height:1.45}
.up{color:var(--up)}.dn{color:var(--dn)}.fl{color:#c9d2e0}
/* cover */
.cover h1{font-size:104px;margin-top:40px;letter-spacing:-3px}
.chips{margin-top:auto;display:flex;flex-direction:column;gap:16px}
.chip{background:var(--card);border:1.5px solid var(--line);border-radius:22px;padding:22px 28px;font-size:31px;font-weight:700}
.chip b{font-weight:900}
.swipe{align-self:flex-end;margin-top:22px;font-size:26px;color:var(--hl);font-weight:800;letter-spacing:.5px}
.cover .chip{margin-right:70px}
.peek{position:absolute;right:-142px;top:300px;width:110px;height:480px;border-radius:28px;background:var(--card2);
 border:1.5px solid var(--line);opacity:.9}
/* tiles */
.tiles{margin-top:38px;display:grid;grid-template-columns:1fr 1fr;gap:20px}
.tile{background:var(--card);border:1.5px solid var(--line);border-radius:26px;padding:26px 28px 24px;position:relative;overflow:hidden}
.tile.wide{grid-column:1 / span 2}
.tile .n{font-size:27px;color:var(--mut);font-weight:700}
.tile .v{font-size:52px;font-weight:900;letter-spacing:-1px;margin-top:6px}
.tile .c{font-size:30px;font-weight:900;margin-top:2px}
.tile .note{font-size:22px;color:var(--hl);margin-top:10px;font-weight:700}
.bar{height:10px;border-radius:6px;background:#1d2a45;margin-top:16px;overflow:hidden}
.bar i{display:block;height:100%;border-radius:6px}
.bar i.up{background:var(--up)}.bar i.dn{background:var(--dn)}
/* points */
.pts{margin-top:40px;display:flex;flex-direction:column;gap:22px;counter-reset:pt}
.pt{background:var(--card);border:1.5px solid var(--line);border-radius:26px;padding:26px 30px 24px 104px;position:relative;counter-increment:pt}
.pt::before{content:counter(pt,decimal-leading-zero);position:absolute;left:28px;top:24px;font-size:40px;font-weight:900;color:var(--acc)}
.pt h3{font-size:37px;font-weight:900;line-height:1.3}
.pt p{font-size:29px;color:#c3cede;line-height:1.5;margin-top:10px}
.pt small{display:block;font-size:20px;color:var(--dim);margin-top:12px;font-weight:600}
/* sources / outro */
.src{margin-top:30px;background:var(--card);border:1.5px solid var(--line);border-radius:26px;padding:26px 32px;
 font-size:22px;color:#b8c4d6;line-height:1.7;list-style:none}
.src li::before{content:"·  ";color:var(--acc)}
.cta{margin-top:auto;background:linear-gradient(135deg,#1c3a6e,#13254a);border-radius:26px;padding:30px 34px;border:1.5px solid #2f5596}
.cta b{display:block;font-size:36px;font-weight:900}
.cta span{display:block;font-size:25px;color:#c9d9f5;margin-top:8px}
/* footer */
.disc{position:absolute;left:72px;right:72px;bottom:150px;font-size:20px;color:var(--dim);
 display:flex;justify-content:space-between}
.prog{position:absolute;left:72px;right:72px;bottom:64px;height:6px;border-radius:4px;background:#1a2640}
.prog i{display:block;height:100%;border-radius:4px;background:var(--acc)}
"""

LOGO = """<svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="50" fill="#16233a"/>
<rect x="24" y="52" width="13" height="24" rx="3" fill="#4d9bff" opacity=".55"/>
<rect x="43" y="42" width="13" height="34" rx="3" fill="#4d9bff" opacity=".8"/>
<rect x="62" y="30" width="13" height="46" rx="3" fill="#4d9bff"/>
<path d="M22 44 L34 56 L78 22" fill="none" stroke="#f2f5fa" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/></svg>"""

def hl_title(t):
    """제목에서 [[...]] 로 감싼 부분을 강조색으로 (데이터에 없으면 그대로)."""
    return re.sub(r"\[\[(.+?)\]\]", lambda m: f"<em>{m.group(1)}</em>", E(t))

def page(inner, i, n, cls=""):
    hd = E(data.get("handle") or "")
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head>
<body class="{cls}"><div class="bgglow"></div>
<div class="top"><div class="brand">{LOGO}<span>{hd}</span></div><span>{E(data['date'])}</span></div>
<div class="safe">{inner}</div>
<div class="disc"><span>기사·공식 데이터 기반 · 독립 재검증 · 투자 권유 아님</span><span>{i} / {n}</span></div>
<div class="prog"><i style="width:{i/n*100:.1f}%"></i></div></body></html>"""

slides = []
c = data["cover"]
chips = "".join(f'<div class="chip">{colorize(k)}</div>' for k in c["points"])
slides.append(("cover", f'<div class="tag">{E(c["tag"])}</div><h1>{hl_title(c["title"])}</h1>'
               f'<div class="sub">{E(c["sub"])}</div><div class="chips">{chips}</div>'
               '<div class="swipe">넘겨서 보기 →</div><div class="peek"></div>'))
for s in data["slides"]:
    body = f'<div class="tag">{E(s["tag"])}</div><h1>{hl_title(s["title"])}</h1>'
    if s.get("sub"): body += f'<div class="sub">{E(s["sub"])}</div>'
    if s.get("rows"):
        rows = s["rows"]; tiles = []
        for k, r in enumerate(rows):
            wide = " wide" if (len(rows) % 2 == 1 and k == len(rows) - 1) or len(rows) <= 2 else ""
            p = pct(r["chg"]); bar = ""
            if p is not None:
                w = min(100, max(6, p / 3 * 100))
                bar = f'<div class="bar"><i class="{tone(r["chg"])}" style="width:{w:.0f}%"></i></div>'
            note = f'<div class="note">{E(r["note"])}</div>' if r.get("note") else ""
            tiles.append(f'<div class="tile{wide}"><div class="n">{E(r["name"])}</div><div class="v">{E(r["value"])}</div>'
                         f'<div class="c {tone(r["chg"])}">{arrow(r["chg"])} {E(r["chg"])}</div>{bar}{note}</div>')
        body += '<div class="tiles">' + "".join(tiles) + '</div>'
    if s.get("points"):
        body += '<div class="pts">' + "".join(
            f'<div class="pt"><h3>{colorize(p["head"])}</h3><p>{colorize(p["body"])}</p><small>출처 · {E(p["src"])}</small></div>'
            for p in s["points"]) + '</div>'
    slides.append(("", body))
srcs = "".join(f"<li>{E(x)}</li>" for x in data["sources"])
hd = E(data.get("handle") or "")
slides.append(("", f'<div class="tag">SOURCES</div><h1>오늘의 출처</h1><ul class="src">{srcs}</ul>'
               f'<div class="cta"><b>매일 아침, 팩트로만 보는 시장</b><span>팔로우 {hd} · 저장해두고 다음 날과 비교해보세요</span></div>'))

n = len(slides)
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1080, "height": 1350})
    for i, (cls, inner) in enumerate(slides, 1):
        pg.set_content(page(inner, i, n, cls), wait_until="load")
        pg.screenshot(path=f"{out}/{i:02d}.jpg", type="jpeg", quality=85)
    b.close()
open(f"{out}/caption.txt", "w", encoding="utf-8").write(data["caption"])
assert len(data["caption"]) <= 2200 and data["caption"].count("#") <= 30, "caption too long / too many hashtags"
assert n <= 10, "carousel max 10"
json.dump({"images": [f"{i:02d}.jpg" for i in range(1, n + 1)], "caption_file": "caption.txt", "approved": False},
          open(f"{out}/manifest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"rendered {n} slides -> {out}")
