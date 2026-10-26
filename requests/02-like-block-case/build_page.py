"""Build the like-block page in eight languages (content_<lang>.json). Run stats.py first.

    python build_page.py         artifact: one file, out/like-block.html, every image inlined
    python build_page.py site    the site area servoom.pages.dev/bots/:
                                 docs/public/bots/{index.html,bots.js,bots.css} in this repo and
                                 data/bots/{avatars.webp,accounts.json,pairs/*.png} in the sibling
                                 servoom-stats checkout, whose data/ the site build downloads
                                 (docs/scripts/fetch-stats.mjs). Third-party images never enter
                                 this repository.
"""
import base64, html, io, json, shutil, sys
from pathlib import Path
from PIL import Image

HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]; OUT = HERE / "out"; AV = OUT / "avatars"
PAIRS_DIR = ROOT / "requests/01-check-divoom-accounts-bots/out/pairs"
SITE = ROOT / "docs/public/bots"
STATS = ROOT.parent / "servoom-stats"
DATA_URL = "../stats/data/bots"           # where the site serves the stats repo's data/bots/
LANGS = ["en", "es", "zh", "ja", "ru", "de", "fr", "pt"]
LOCALE = {"en": "en-US", "es": "es-ES", "zh": "zh-CN", "ja": "ja-JP", "ru": "ru-RU", "de": "de-DE", "fr": "fr-FR", "pt": "pt-BR"}
SPRITE_COLS = 50                           # the avatar sheet: 16-px cells, row-major, in list order

MODE = sys.argv[1] if len(sys.argv) > 1 else "artifact"
assert MODE in ("artifact", "site"), MODE

N = json.loads((OUT / "numbers.json").read_text(encoding="utf-8"))
T = {l: json.loads((HERE / f"content_{l}.json").read_text(encoding="utf-8")) for l in LANGS}
for l in LANGS: T[l].pop("_meta", None)
missing = {l: [k for k in T["en"] if k not in T[l]] for l in LANGS}
assert not any(missing.values()), missing
prof = {json.loads(x)["uid"]: json.loads(x) for x in (ROOT / "requests/01-check-divoom-accounts-bots/out/block_profiles.jsonl").open(encoding="utf-8")}
arts_n = {json.loads(x)["uid"]: len(json.loads(x)["arts"] or []) for x in (OUT / "block_arts.jsonl").open(encoding="utf-8")}
pairs = json.loads((OUT / "pairs_examples.json").read_text(encoding="utf-8"))
camp = json.loads((OUT / "campaign_comments.json").read_text(encoding="utf-8"))

def png_uri(path, size=None):
    im = Image.open(path).convert("RGB")
    if size: im = im.resize((size, size), Image.NEAREST)
    b = io.BytesIO(); im.save(b, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()
def esc(s): return html.escape(str(s), quote=True)

# accounts array: [uid, name, level, score, likes, fans, country, arts, avatar]
# avatar = data URI (artifact) or 1/0 (site: the sprite sheet holds every account in this order)
accounts = []
for uid in sorted(prof):
    p = prof[uid]; av = AV / f"{uid}.png"
    avatar = (png_uri(av) if av.exists() else "") if MODE == "artifact" else int(av.exists())
    accounts.append([uid, p.get("NickName") or "", p.get("Level"), p.get("Score"), p.get("LikeCnt"), p.get("FansCnt"),
                     p.get("CountryISOCode") or "", arts_n.get(uid, 0), avatar])
SPRITE_ROWS = -(-len(accounts) // SPRITE_COLS)
PITCH = 17                                 # a 16-px cell plus a 1-px transparent gutter; 1-px margin all around

def avatar_html(uid, size, alt=""):
    """Drew's profile picture: an inline image, or a canvas the page fills from the sprite sheet."""
    if MODE == "artifact":
        return f'<img src="{png_uri(AV / f"{uid}.png", size)}" alt="{esc(alt)}">'
    idx = next(i for i, a in enumerate(accounts) if a[0] == uid)
    return f'<canvas class="av" width="16" height="16" data-i="{idx}" role="img" aria-label="{esc(alt)}"></canvas>'

def pair_src(p, key):
    if MODE == "artifact":
        return png_uri(PAIRS_DIR / p[key], 112)
    return f"{DATA_URL}/pairs/{p[key]}"

# id-existence chart data (sweep of 4 Oct 2026, slices of 400 ids)
EX = [(400961852,0.88,0.385),(400962252,0.91,0.325),(400962652,0.95,0.175),(400963052,0.99,0.165),(400963452,0.875,0.385),(400963852,0.915,0.235),(400964252,0.895,0.295),(400964652,0.81,0.535),(400965052,0.975,0.11),(400965452,0.86,0.45),(400965852,0.825,0.45),(400966252,0.99,0.125),(400966652,0.75,0.575),(400967052,0.81,0.45),(400967452,0.92,0.215),(400967852,0.85,0.395),(400968252,0.73,0.56),(400968652,0.905,0.27),(400969052,0.825,0.43),(400969452,0.735,0.545),(400969852,0.995,0.065),(400970252,0.855,0.405),(400970652,0.79,0.45),(400971052,0.99,0.065),(400971452,0.875,0.375),(400971852,0.0,1.0),(400972252,0.0,1.0),(400972652,0.0,1.0),(400973052,0.0,1.0),(400973452,0.0,1.0),(400973852,0.0,1.0),(400974252,0.0,1.0),(400974652,0.0,1.0),(400975052,0.0,1.0),(400975452,0.005,1.0),(400975852,0.83,0.49),(400976252,0.98,0.145),(400976652,0.985,0.09),(400977052,0.87,0.41),(400977452,0.925,0.245),(400977852,0.99,0.045),(400978252,0.81,0.465),(400978652,0.75,0.51),(400979052,0.98,0.08),(400979452,0.765,0.515),(400979852,0.905,0.35),(400980252,0.95,0.21),(400980652,0.925,0.25),(400981052,0.78,0.535),(400981452,0.855,0.375),(400981852,0.92,0.165),(400982252,0.775,0.465),(400982652,0.975,0.14),(400983052,0.93,0.24),(400983452,0.805,0.455),(400983852,0.98,0.13),(400984252,0.945,0.205),(400984652,0.895,0.375),(400985052,0.975,0.125),(400985452,0.889,0.3)]
def ex_svg(idx, color):
    W, H, n = 820, 90, len(EX); bw = W / n
    s = [f'<svg viewBox="0 0 {W} {H}" class="exsvg" aria-hidden="true">']
    for i, d in enumerate(EX):
        v = d[idx]; h = max(2, v * (H - 14)); x = i * bw + 1
        s.append(f'<rect x="{x:.1f}" y="{H-14-h:.1f}" width="{bw-2:.1f}" height="{h:.1f}" fill="var({color})"/>')
    s.append(f'<line x1="0" x2="{W}" y1="{H-14}" y2="{H-14}" stroke="var(--line)"/>')
    for i in (0, 25, 35, n - 1):
        s.append(f'<text x="{i*bw+bw/2:.0f}" y="{H-2}" text-anchor="middle">{EX[i][0]:,}</text>')
    return "".join(s) + "</svg>"

def pair_card(p):
    return (f'<figure class="pair"><div class="imgs">'
            f'<div class="tile"><img src="{pair_src(p, "bot_png")}" alt="" width="112" height="112" loading="lazy"><span class="tag bot" data-t="pair_copy"></span></div>'
            f'<div class="tile"><img src="{pair_src(p, "orig_png")}" alt="" width="112" height="112" loading="lazy"><span class="tag" data-t="pair_original"></span></div></div>'
            f'<figcaption><b>{esc(p["title"]) or "(untitled)"}</b>'
            f'<span><span data-t="pair_in"></span> {esc(p["bot"])} · <span data-t="pair_by"></span> {esc(p["author"])}</span>'
            f'<span><span data-t="pair_time"></span> <time data-ts="{p["date"]}"></time></span>'
            f'<span class="mono">{p["bytes"]} B · md5 {p["md5"][:12]}</span></figcaption></figure>')
drew_pairs = [p for p in pairs if p["bot"] == "Drew"][:3]

def comment_rows(gid, flag):
    rows = []
    for x in camp[str(gid)]:
        u = x.get("UserId", 0)
        if 400971852 <= u <= 400975850 and str(x.get("RobertFlag")) == flag:
            rows.append((x["Date"], u, x.get("Comment") or x.get("Content") or "", x.get("RobertFlag")))
    rows.sort()
    return rows
rob = comment_rows(1343491, "1")
c26 = comment_rows(4333583, "0")[:8]
def ctable(rows):
    out = ['<div class="scroll"><table><thead><tr><th data-t="e5_th_time"></th><th data-t="e5_th_acct"></th><th data-t="e5_th_text"></th><th data-t="e5_th_flag"></th></tr></thead><tbody>']
    for d, u, txt, fl in rows:
        out.append(f'<tr><td><time data-ts="{d}" data-fmt="dt"></time></td><td class="mono">{u}</td><td class="txt">{esc(txt)}</td><td>{esc(fl)}</td></tr>')
    return "".join(out) + "</tbody></table></div>"

tl = "".join(f'<dt data-t="tl_{i}d"></dt><dd data-t="tl_{i}"></dd>' for i in range(1, 8))
e3rows = "".join(f'<tr><td data-t="e3_r{i}"></td><td data-t="e3_r{i}b"></td><td data-t="e3_r{i}r"></td></tr>' for i in range(1, 9))
langbtns = "".join(f'<button type="button" class="lb" data-lang="{l}" id="lang-{l}">{esc(T[l]["lang_name"])}</button>' for l in LANGS)
langopts = "".join(f'<option value="{l}">{esc(T[l]["lang_name"])}</option>' for l in LANGS)

# ---------------------------------------------------------------------------------- styles
CSS = """/* Layout: a single reading column with evidence sections; pixel-art thumbnails on dark tiles; a 2,000-avatar mosaic; one accent (block orange) against a cool neutral. */
:root {
  --bg:#f3f4f6; --surface:#ffffff; --fg:#161a20; --fg2:#4a5260; --muted:#737b88; --line:#dadfe6;
  --block:#e2641c; --block-bg:#fdeee4; --people:#2466b8; --people-bg:#e6eef9; --ok:#1f8a4c;
  --display:"Pixelify Sans","Courier New",monospace;
  --body:"Noto Sans","Segoe UI","Helvetica Neue",Arial,"Noto Sans SC","Noto Sans JP","PingFang SC","Hiragino Sans","Microsoft YaHei","Meiryo",sans-serif;
  --mono:ui-monospace,"Cascadia Mono",Consolas,"Noto Sans Mono",monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg:#12151a; --surface:#1a1e25; --fg:#eceef2; --fg2:#b5bcc8; --muted:#8a93a1; --line:#2c323c;
  --block:#f2822f; --block-bg:#3a2415; --people:#5b9ae6; --people-bg:#1b2a40; --ok:#4fc27a; color-scheme:dark } }
:root[data-theme="dark"] {
  --bg:#12151a; --surface:#1a1e25; --fg:#eceef2; --fg2:#b5bcc8; --muted:#8a93a1; --line:#2c323c;
  --block:#f2822f; --block-bg:#3a2415; --people:#5b9ae6; --people-bg:#1b2a40; --ok:#4fc27a; color-scheme:dark }
* { box-sizing:border-box }
body { margin:0; background:var(--bg); color:var(--fg); font-family:var(--body); font-size:16px; line-height:1.6 }
.wrap { max-width:800px; margin:0 auto; padding-inline:20px; padding-block:28px 72px; display:flex; flex-direction:column; gap:48px }
section, header.lead { display:flex; flex-direction:column; gap:14px; min-width:0 }
h1,h2,h3 { margin:0; line-height:1.2; text-wrap:balance }
h1 { font-size:clamp(1.9rem,5.5vw,2.8rem); font-weight:700; letter-spacing:-.01em }
h2 { font-size:1.45rem; font-weight:700 }
h3 { font-size:1.05rem; font-weight:700 }
p { margin:0; max-width:68ch }
ul { margin:0; padding-left:1.2em; max-width:68ch; display:flex; flex-direction:column; gap:8px }
.eyebrow { font-family:var(--display); font-size:.9rem; letter-spacing:.06em; text-transform:uppercase; color:var(--block) }
.lede { font-size:1.15rem; color:var(--fg2); max-width:62ch }
.langbar { display:flex; flex-wrap:wrap; gap:6px; align-items:center }
.langbar .ll { font-size:.8rem; color:var(--muted); margin-right:4px }
.lb { font:inherit; font-size:.85rem; padding:4px 10px; border:1px solid var(--line); background:var(--surface); color:var(--fg2); border-radius:999px; cursor:pointer }
.lb[aria-pressed="true"] { background:var(--fg); color:var(--bg); border-color:var(--fg) }
.lb:focus-visible, .lb:hover { border-color:var(--block) }
.verdict { border-left:5px solid var(--block); background:var(--block-bg); padding:16px 20px; display:flex; flex-direction:column; gap:8px; border-radius:0 6px 6px 0 }
.verdict .vl { font-family:var(--display); font-size:.9rem; letter-spacing:.06em; text-transform:uppercase; color:var(--block) }
.tiles { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:1px; background:var(--line); border:1px solid var(--line) }
.tile-s { background:var(--surface); padding:14px 16px; display:flex; flex-direction:column; gap:4px; min-width:0 }
.tile-s .v { font-family:var(--display); font-size:2rem; line-height:1.1; color:var(--block); font-variant-numeric:tabular-nums }
.tile-s .l { font-weight:500; font-size:.92rem }
.tile-s .s { font-size:.8rem; color:var(--muted) }
figure { margin:0; background:var(--surface); border:1px solid var(--line); border-radius:6px; padding:16px; display:flex; flex-direction:column; gap:10px; min-width:0 }
figcaption { font-size:.82rem; color:var(--muted); max-width:75ch }
.ftitle { font-weight:600; font-size:.95rem }
.profile { display:flex; gap:16px; align-items:flex-start; flex-wrap:wrap }
.profile img, .profile .av { width:96px; height:96px; image-rendering:pixelated; border:1px solid var(--line); background-color:#000; flex:0 0 auto }
.profile .pname { font-weight:700; font-size:1.2rem }
.profile .pstats { color:var(--fg2); font-size:.9rem }
.gallery { display:grid; grid-template-columns:repeat(auto-fill,minmax(270px,1fr)); gap:12px }
.pair { padding:12px }
.pair .imgs { display:flex; gap:8px }
.tile { position:relative; flex:0 0 auto }
.tile img { display:block; width:104px; height:104px; image-rendering:pixelated; border:1px solid var(--line); background:#000 }
.tag { position:absolute; left:4px; bottom:4px; font-family:var(--display); font-size:.7rem; letter-spacing:.05em; text-transform:uppercase; padding:1px 6px; background:rgba(255,255,255,.92); color:#161a20; border-radius:2px }
.tag.bot { background:var(--block); color:#fff }
.pair figcaption { display:grid; gap:2px; font-size:.8rem }
.pair figcaption b { color:var(--fg); font-size:.9rem }
.mono { font-family:var(--mono); font-size:.85em }
.scroll { overflow-x:auto }
table { border-collapse:collapse; width:100%; font-size:.86rem; font-variant-numeric:tabular-nums }
th,td { padding:7px 10px; text-align:left; border-bottom:1px solid var(--line); vertical-align:top }
th { font-weight:600; color:var(--muted); font-size:.78rem; text-transform:uppercase; letter-spacing:.04em; white-space:nowrap }
td.num, th.num { text-align:right; white-space:nowrap }
td.txt { min-width:16ch }
tbody tr:last-child td { border-bottom:0 }
.exsvg { width:100%; height:auto; display:block }
.exsvg text { font-family:var(--mono); font-size:11px; fill:var(--muted) }
.sub { font-size:.8rem; color:var(--fg2); font-weight:500 }
.share { display:flex; height:28px; border-radius:4px; overflow:hidden; border:1px solid var(--line) }
.share div { display:flex; align-items:center; justify-content:center; font-family:var(--display); font-size:.9rem; color:#fff; min-width:0 }
.share .b { background:var(--block) } .share .o { background:var(--people) }
.legend { display:flex; flex-wrap:wrap; gap:6px 18px; font-size:.82rem; color:var(--fg2) }
.legend i { display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:6px }
.mosaic { display:grid; grid-template-columns:repeat(auto-fill,minmax(14px,1fr)); gap:1px; background:var(--line); border:1px solid var(--line) }
.mosaic img, .mosaic .av { display:block; width:100%; aspect-ratio:1; image-rendering:pixelated; background-color:#000 }
.mosaic .none { background:var(--surface); aspect-ratio:1 }
.tl { display:grid; grid-template-columns:auto 1fr; gap:8px 16px; margin:0; max-width:74ch }
.tl dt { font-family:var(--display); font-size:.9rem; color:var(--block); white-space:nowrap; padding-top:2px }
.tl dd { margin:0; color:var(--fg2) }
.hyp { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:1px; background:var(--line); border:1px solid var(--line) }
.hyp > div { background:var(--surface); padding:14px; display:flex; flex-direction:column; gap:6px; font-size:.9rem; color:var(--fg2); min-width:0 }
.hyp .k { font-family:var(--display); font-size:.8rem; letter-spacing:.05em; text-transform:uppercase; color:var(--muted) }
.hyp .k.fit { color:var(--ok) }
.hyp b { color:var(--fg); font-size:.98rem }
.ask { border:2px solid var(--block); padding:16px 20px; border-radius:6px; display:flex; flex-direction:column; gap:8px }
.search { display:flex; gap:10px; align-items:center; flex-wrap:wrap }
.search input { font:inherit; padding:8px 12px; border:1px solid var(--line); border-radius:6px; background:var(--surface); color:var(--fg); flex:1 1 240px; min-width:0 }
.search .cnt { font-size:.85rem; color:var(--muted) }
#list img, #list .av { width:24px; height:24px; max-width:none; image-rendering:pixelated; display:block; background-color:#000 }
#list td { padding:4px 8px }
#list td:first-child, #list th:first-child { width:32px; min-width:32px }
#list tbody tr { cursor:pointer }
#list tbody tr:hover td { background:var(--people-bg) }
#list tbody tr.on td { background:var(--block-bg) }
#list tbody tr:focus-visible { outline:2px solid var(--block); outline-offset:-2px }
.pager { display:flex; gap:8px; align-items:center; flex-wrap:wrap }
.pager button { font:inherit; font-size:.9rem; padding:6px 12px; border:1px solid var(--line); background:var(--surface); color:var(--fg); border-radius:6px; cursor:pointer }
.pager button:disabled { opacity:.4; cursor:default }
.pager button:not(:disabled):hover { border-color:var(--block) }
.pager .cnt { font-size:.85rem; color:var(--muted); font-variant-numeric:tabular-nums; padding-inline:4px }
.detail { display:flex; gap:20px; align-items:flex-start; flex-wrap:wrap; background:var(--surface); border:2px solid var(--block); border-radius:6px; padding:16px }
.detail img, .detail .av, .detail .none { width:160px; height:160px; max-width:none; image-rendering:pixelated; border:1px solid var(--line); background-color:#000; flex:0 0 auto; display:block }
.detail .none { background:var(--bg) }
.detail .dname { font-weight:700; font-size:1.5rem; line-height:1.2; overflow-wrap:anywhere }
.detail .did { color:var(--muted) }
.detail dl { display:grid; grid-template-columns:auto auto; gap:4px 14px; margin:10px 0 0; font-size:.9rem }
.detail dt { color:var(--muted) } .detail dd { margin:0; font-variant-numeric:tabular-nums }
.method { font-size:.9rem; color:var(--fg2) }
.foot { font-size:.85rem; color:var(--muted); border-top:1px solid var(--line); padding-top:14px }
a { color:var(--people) }
time { white-space:nowrap }
@media (max-width:480px) { .tile img { width:88px; height:88px } .wrap { padding-inline:16px } }
@media (prefers-reduced-motion: reduce) { * { transition:none !important } }
"""

# The site adds the servoom header and footer (same markup as the landing page, colored
# with this page's palette) and draws avatars from one sprite sheet instead of 2,000 images.
SITE_CSS = f"""
/* servoom.pages.dev/bots/ — generated by requests/02-like-block-case/build_page.py site; edit there. */
header.top {{ display:flex; align-items:center; gap:12px 20px; flex-wrap:wrap; padding:14px 20px; border-bottom:1px solid var(--line); background:var(--surface) }}
.brand {{ font-weight:700; font-size:1.15rem; color:var(--fg); text-decoration:none; letter-spacing:.01em }}
.pillars {{ display:flex; gap:4px; flex:1; flex-wrap:wrap }}
.pillars a {{ color:var(--fg2); text-decoration:none; padding:6px 12px; border-radius:6px; white-space:nowrap }}
.pillars a.on {{ background:var(--people-bg); color:var(--fg) }}
.pillars a:hover {{ color:var(--fg) }}
select {{ background:var(--surface); color:var(--fg); border:1px solid var(--line); border-radius:6px; padding:6px 8px; font:inherit; font-size:.9rem }}
footer.site {{ border-top:1px solid var(--line); padding:20px; text-align:center; color:var(--muted); font-size:.82rem; display:flex; flex-direction:column; gap:4px }}
footer.site a {{ color:var(--fg2) }}
canvas.av {{ image-rendering:pixelated; background:#000 }}
/* The mosaic is the sprite sheet itself (every account, {SPRITE_COLS} per row, in list order), with a hover grid over it. */
.mosaic {{ display:block; position:relative; padding:0; overflow-x:auto; background:var(--surface) }}
.mosaic img {{ display:block; width:100%; min-width:560px; height:auto; aspect-ratio:auto; image-rendering:pixelated; background:var(--surface) }}
.mosaic .grid {{ position:absolute; inset:0; min-width:560px; display:grid; grid-template-columns:repeat({SPRITE_COLS},1fr) }}
.mosaic .grid div:hover {{ outline:2px solid var(--block); outline-offset:-1px }}
.wait {{ color:var(--muted); font-size:.9rem; border:1px dashed var(--line); border-radius:6px; padding:18px; text-align:center }}
"""

# ---------------------------------------------------------------------------------- body
def mosaic():
    if MODE == "artifact":
        return '<div class="mosaic" id="mosaic"></div>'
    return (f'<div class="mosaic" id="mosaic"><img src="{DATA_URL}/avatars.webp" width="{SPRITE_COLS * PITCH + 1}" height="{SPRITE_ROWS * PITCH + 1}" alt="" loading="lazy">'
            f'<div class="grid" id="grid"></div></div>')

def body():
    lead = (f'<div class="langbar" role="group" aria-label="Language"><span class="ll" data-t="lang_label"></span>{langbtns}</div>'
            if MODE == "artifact" else "")
    return f"""<div class="wrap">
<header class="lead">
  {lead}
  <div class="eyebrow" data-t="eyebrow"></div>
  <h1 data-t="h1"></h1>
  <p class="lede" data-t="lede"></p>
  <div class="verdict"><div class="vl" data-t="verdict_label"></div><p data-t="verdict_1"></p><p data-t="verdict_2"></p></div>
  <div class="tiles">
    <div class="tile-s"><span class="v" data-n="n_accounts"></span><span class="l" data-t="tile_accounts"></span><span class="s" data-t="tile_accounts_s"></span></div>
    <div class="tile-s"><span class="v" data-n="n_arts"></span><span class="l" data-t="tile_arts"></span><span class="s" data-t="tile_arts_s"></span></div>
    <div class="tile-s"><span class="v" data-n="pct_block_new" data-suffix="%"></span><span class="l" data-t="tile_likes"></span><span class="s" data-t="tile_likes_s"></span></div>
    <div class="tile-s"><span class="v">25 / 25</span><span class="l" data-t="tile_robot"></span><span class="s" data-t="tile_robot_s"></span></div>
  </div>
</header>

<section>
  <div class="eyebrow" data-t="how_label"></div>
  <p data-t="how_1"></p><p data-t="how_2"></p>
</section>

<section>
  <div class="eyebrow" data-t="ex_label"></div>
  <h2 data-t="ex_h2"></h2>
  <figure><div class="profile">{avatar_html(N['drew_id'], 96, "Drew's avatar")}<div><div class="pname">Drew <span class="mono">· {N['drew_id']}</span></div><div class="pstats" data-t="ex_stats"></div></div></div></figure>
  <p data-t="ex_1"></p>
  <ul><li data-t="ex_li1"></li><li data-t="ex_li2"></li><li data-t="ex_li3"></li><li data-t="ex_li4"></li></ul>
  <div class="gallery">{''.join(pair_card(p) for p in drew_pairs)}</div>
  <p class="sub" data-t="ex_caption"></p>
</section>

<section>
  <div class="eyebrow" data-t="e1_label"></div>
  <h2 data-t="e1_h2"></h2>
  <p data-t="e1_1"></p><p data-t="e1_2"></p>
  <figure><div class="ftitle" data-t="e1_fig"></div>
    <div class="sub" data-t="e1_fig_odd"></div>{ex_svg(1, '--people')}
    <div class="sub" data-t="e1_fig_even"></div>{ex_svg(2, '--block')}
    <figcaption data-t="e1_cap"></figcaption></figure>
</section>

<section>
  <div class="eyebrow" data-t="e2_label"></div>
  <h2 data-t="e2_h2"></h2>
  <p data-t="e2_1"></p><p data-t="e2_2"></p><p data-t="e2_3"></p>
  <div class="ftitle" data-t="e2_fig"></div>
  <div class="gallery">{''.join(pair_card(p) for p in pairs)}</div>
  <p class="sub" data-t="e2_cap"></p>
</section>

<section>
  <div class="eyebrow" data-t="e3_label"></div>
  <h2 data-t="e3_h2"></h2>
  <p data-t="e3_1"></p><p data-t="e3_2"></p>
  <figure><div class="ftitle" data-t="e3_table"></div><div class="scroll"><table><thead><tr><th data-t="e3_th_prop"></th><th data-t="e3_th_block"></th><th data-t="e3_th_rand"></th></tr></thead><tbody>{e3rows}</tbody></table></div></figure>
  <figure><div class="ftitle" data-t="e3_mosaic"></div>{mosaic()}<figcaption data-t="e3_mosaic_cap"></figcaption></figure>
</section>

<section>
  <div class="eyebrow" data-t="e4_label"></div>
  <h2 data-t="e4_h2"></h2>
  <p data-t="e4_1"></p>
  <figure><div class="ftitle" data-t="e4_fig"></div>
    <div class="share"><div class="b" style="width:{N['pct_block_new']}%">{N['pct_block_new']}%</div><div class="o" style="width:{100-N['pct_block_new']:.1f}%">{100-N['pct_block_new']:.1f}%</div></div>
    <div class="legend"><span><i style="background:var(--block)"></i><span data-t="e4_fig_block"></span></span><span><i style="background:var(--people)"></i><span data-t="e4_fig_other"></span></span></div>
    <figcaption data-t="e4_cap"></figcaption></figure>
  <p data-t="e4_2"></p>
  <ul><li data-t="e4_li1"></li><li data-t="e4_li2"></li><li data-t="e4_li3"></li><li data-t="e4_li4"></li><li data-t="e4_li5"></li></ul>
</section>

<section>
  <div class="eyebrow" data-t="e5_label"></div>
  <h2 data-t="e5_h2"></h2>
  <p data-t="e5_1"></p><p data-t="e5_2"></p>
  <figure><div class="ftitle" data-t="e5_fig"></div>{ctable(rob)}<figcaption data-t="e5_cap"></figcaption></figure>
  <figure><div class="ftitle" data-t="e5_fig2"></div>{ctable(c26)}</figure>
</section>

<section>
  <div class="eyebrow" data-t="tl_label"></div>
  <h2 data-t="tl_h2"></h2>
  <dl class="tl">{tl}</dl>
</section>

<section>
  <div class="eyebrow" data-t="sure_label"></div>
  <h2 data-t="sure_h2"></h2>
  <p data-t="sure_1"></p><p data-t="sure_2"></p>
</section>

<section>
  <div class="eyebrow" data-t="who_label"></div>
  <h2 data-t="who_h2"></h2>
  <p data-t="who_0"></p>
  <div class="hyp">
    <div><span class="k fit" data-t="who_1k"></span><b data-t="who_1h"></b><span data-t="who_1"></span></div>
    <div><span class="k" data-t="who_2k"></span><b data-t="who_2h"></b><span data-t="who_2"></span></div>
    <div><span class="k" data-t="who_3k"></span><b data-t="who_3h"></b><span data-t="who_3"></span></div>
  </div>
  <p data-t="who_4"></p>
</section>

<section>
  <div class="eyebrow" data-t="you_label"></div>
  <h2 data-t="you_h2"></h2>
  <ul><li data-t="you_li1"></li><li data-t="you_li2"></li><li data-t="you_li3"></li><li data-t="you_li4"></li></ul>
</section>

<section>
  <div class="eyebrow" data-t="ask_label"></div>
  <div class="ask"><h2 data-t="ask_h2"></h2><p data-t="ask_1"></p></div>
</section>

<section>
  <div class="eyebrow" data-t="list_label"></div>
  <h2 data-t="list_h2"></h2>
  <p data-t="list_1"></p>
  <p class="sub" data-t="list_pick"></p>
  <div class="search"><input id="q" type="search" autocomplete="off"><span class="cnt" id="cnt"></span></div>
  <div class="scroll"><table id="list"><thead><tr><th></th><th data-t="list_th_id"></th><th data-t="list_th_name"></th><th class="num" data-t="list_th_level"></th><th class="num" data-t="list_th_score"></th><th class="num" data-t="list_th_likes"></th><th class="num" data-t="list_th_fans"></th><th data-t="list_th_country"></th><th class="num" data-t="list_th_arts"></th></tr></thead><tbody id="lb"></tbody></table></div>
  <div class="pager"><button type="button" id="pg-first" data-t="list_first"></button><button type="button" id="pg-prev" data-t="list_prev"></button><span class="cnt" id="pg-info"></span><button type="button" id="pg-next" data-t="list_next"></button><button type="button" id="pg-last" data-t="list_last"></button></div>
  <div class="detail" id="detail" hidden></div>
</section>

<section class="method">
  <div class="eyebrow" data-t="method_label"></div>
  <h2 data-t="method_h2"></h2>
  <ul><li data-t="method_li1"></li><li data-t="method_li2"></li><li data-t="method_li3"></li><li data-t="method_li4"></li><li data-t="method_li5"></li><li data-t="method_li6"></li></ul>
</section>

<section class="foot">
  <h3 data-t="about_h2"></h3>
  <p data-t="about_1"></p>
</section>
</div>
"""

# ---------------------------------------------------------------------------------- script
def script():
    """Rendering: the strings of the chosen language, the number formats, the mosaic and the
    searchable list. The artifact carries the accounts inline with their avatars as data
    URIs; the site fetches accounts.json and shows cells of the sprite sheet."""
    if MODE == "artifact":
        data = f"const A={json.dumps(accounts, ensure_ascii=False)};"
        av_fn = ('const avHtml=(a,i,attrs)=>a[8]?`<img src="${a[8]}" alt=""${attrs}>`:`<div class="none"${attrs}></div>`;'
                 'function paint(){}')
        mosaic_js = '''mo.innerHTML=A.map((a,i)=>avHtml(a,i,ttl(a)+' loading="lazy"')).join("")'''
    else:
        data = f'let A=[];const SPR={{cols:{SPRITE_COLS},pitch:{PITCH}}};const sheet=new Image();sheet.src="{DATA_URL}/avatars.webp";'
        # list avatars are small canvases; each crops its cell out of the sheet once that is decoded
        av_fn = ('const avHtml=(a,i,attrs)=>a[8]?`<canvas class="av" width="16" height="16" data-i="${i}"${attrs}></canvas>`:`<span class="av none"${attrs}></span>`;'
                 'function paint(){if(!sheet.complete||!sheet.naturalWidth)return;document.querySelectorAll("canvas.av[data-i]").forEach(c=>{const i=+c.dataset.i;'
                 'c.getContext("2d").drawImage(sheet,1+(i%SPR.cols)*SPR.pitch,1+Math.floor(i/SPR.cols)*SPR.pitch,16,16,0,0,16,16);c.removeAttribute("data-i")})}'
                 'sheet.addEventListener("load",paint);')
        mosaic_js = 'document.getElementById("grid").innerHTML=A.map(a=>`<div${ttl(a)}></div>`).join("")'
    lang_ui = ('document.querySelectorAll(".lb").forEach(b=>b.setAttribute("aria-pressed",b.dataset.lang===lang?"true":"false"));'
               if MODE == "artifact" else
               'document.getElementById("lang").value=lang;'
               'document.querySelectorAll("[data-nav]").forEach(el=>{el.textContent=t[el.dataset.nav]??T.en[el.dataset.nav]??""});')
    lang_events = ('document.querySelectorAll(".lb").forEach(b=>b.addEventListener("click",()=>setLang(b.dataset.lang,true)));'
                   if MODE == "artifact" else
                   'document.getElementById("lang").addEventListener("change",e=>setLang(e.target.value,true));')
    load = ("renderMosaic();" if MODE == "artifact" else
            f'fetch("{DATA_URL}/accounts.json").then(r=>{{if(!r.ok)throw new Error(r.status);return r.json()}})'
            '.then(d=>{A=d.rows;renderMosaic();renderList()})'
            '.catch(()=>{mo.innerHTML=`<div class="wait">${(T[lang]||T.en).list_wait||T.en.list_wait||""}</div>`});')
    return f"""const T={json.dumps(T, ensure_ascii=False)};
const N={json.dumps(N)};
{data}
const LOC={json.dumps(LOCALE)};
const LANGS={json.dumps(LANGS)};
let lang="en";
const nf=()=>new Intl.NumberFormat(LOC[lang]);
const dateLong=ts=>new Intl.DateTimeFormat(LOC[lang],{{day:"numeric",month:"long",year:"numeric",timeZone:"UTC"}}).format(new Date(ts*1000));
const dateTime=ts=>new Intl.DateTimeFormat(LOC[lang],{{year:"numeric",month:"short",day:"numeric",hour:"2-digit",minute:"2-digit",timeZone:"UTC",hour12:false}}).format(new Date(ts*1000));
function fill(s){{return s.replace(/\\{{\\{{(\\w+)\\}}\\}}/g,(m,k)=>{{if(k==="crawl_date")return dateLong(Date.UTC(2026,9,9)/1000);const v=N[k];if(v===undefined)return m;return typeof v==="number"?nf().format(v):String(v)}})}}
function render(){{
  const t=T[lang]||T.en;
  document.documentElement.lang=LOC[lang];
  document.title=t.title;
  document.querySelectorAll("[data-t]").forEach(el=>{{const s=t[el.dataset.t]??T.en[el.dataset.t]??"";el.innerHTML=fill(s)}});
  document.querySelectorAll("[data-n]").forEach(el=>{{el.textContent=nf().format(N[el.dataset.n])+(el.dataset.suffix||"")}});
  document.querySelectorAll("time[data-ts]").forEach(el=>{{el.textContent=(el.dataset.fmt==="dt"?dateTime:ts=>dateLong(ts)+" "+new Date(ts*1000).toISOString().slice(11,19)+" UTC")(+el.dataset.ts)}});
  {lang_ui}
  document.getElementById("q").placeholder=t.list_placeholder;
  renderList();
}}
function setLang(l,push){{lang=LANGS.includes(l)?l:"en";try{{localStorage.setItem("servoom-locale",lang)}}catch(e){{}}if(push){{try{{history.replaceState(null,"","#"+lang)}}catch(e){{}}}}render()}}
{lang_events}
{av_fn}
const ttl=a=>` title="${{a[1].replace(/"/g,"&quot;")}} · ${{a[0]}}"`;
// mosaic
const mo=document.getElementById("mosaic");
function renderMosaic(){{{mosaic_js}}}
// list: pages of PAGE rows; the search covers every account; a row opens the detail panel
const PAGE=50;
let page=0,picked=-1;
const q=document.getElementById("q"),lb=document.getElementById("lb"),cnt=document.getElementById("cnt"),info=document.getElementById("pg-info"),detail=document.getElementById("detail");
const pg={{first:document.getElementById("pg-first"),prev:document.getElementById("pg-prev"),next:document.getElementById("pg-next"),last:document.getElementById("pg-last")}};
const tt=k=>fill((T[lang]||T.en)[k]??T.en[k]??"");
const escText=s=>String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;");
function matches(){{const s=q.value.trim().toLowerCase();return A.filter(a=>!s||a[1].toLowerCase().includes(s)||String(a[0]).includes(s))}}
function renderList(){{
  const rows=matches(),f=nf(),pages=Math.max(1,Math.ceil(rows.length/PAGE));
  page=Math.min(page,pages-1);
  const shown=rows.slice(page*PAGE,page*PAGE+PAGE);
  lb.innerHTML=shown.length?shown.map(a=>{{const i=A.indexOf(a);return `<tr data-i="${{i}}" tabindex="0"${{i===picked?' class="on"':""}}><td>${{a[8]?avHtml(a,i,""):""}}</td><td class="mono">${{a[0]}}</td><td>${{escText(a[1])}}</td><td class="num">${{a[2]}}</td><td class="num">${{f.format(a[3])}}</td><td class="num">${{f.format(a[4])}}</td><td class="num">${{a[5]}}</td><td>${{a[6]}}</td><td class="num">${{a[7]}}</td></tr>`}}).join("")
    :`<tr><td colspan="9">${{tt("list_none")}}</td></tr>`;
  cnt.textContent=tt("list_matches").replace("{{{{n}}}}",f.format(rows.length));
  info.textContent=tt("list_page").replace("{{{{p}}}}",f.format(page+1)).replace("{{{{n}}}}",f.format(pages));
  pg.first.disabled=pg.prev.disabled=page===0;
  pg.next.disabled=pg.last.disabled=page>=pages-1;
  renderDetail();
  paint();
}}
function renderDetail(){{
  const a=A[picked];
  detail.hidden=!a;
  if(!a)return;
  const f=nf(),row=(k,v)=>`<dt>${{tt(k)}}</dt><dd>${{v}}</dd>`;
  detail.innerHTML=avHtml(a,picked,"")+`<div><div class="dname">${{escText(a[1])||"&nbsp;"}}</div><div class="did mono">${{tt("list_th_id")}} ${{a[0]}}</div><dl>`
    +row("list_th_level",a[2])+row("list_th_score",f.format(a[3]))+row("list_th_likes",f.format(a[4]))+row("list_th_fans",f.format(a[5]))+row("list_th_country",escText(a[6])||"–")+row("list_th_arts",f.format(a[7]))+`</dl></div>`;
}}
function pick(i){{picked=i;lb.querySelectorAll("tr").forEach(tr=>tr.classList.toggle("on",+tr.dataset.i===i));renderDetail();paint()}}
lb.addEventListener("click",e=>{{const tr=e.target.closest("tr[data-i]");if(tr)pick(+tr.dataset.i)}});
lb.addEventListener("keydown",e=>{{if(e.key==="Enter"||e.key===" "){{const tr=e.target.closest("tr[data-i]");if(tr){{e.preventDefault();pick(+tr.dataset.i)}}}}}});
q.addEventListener("input",()=>{{page=0;renderList()}});
const goTo=p=>{{page=p;renderList();document.getElementById("list").scrollIntoView({{block:"nearest"}})}};
pg.first.addEventListener("click",()=>goTo(0));
pg.prev.addEventListener("click",()=>goTo(page-1));
pg.next.addEventListener("click",()=>goTo(page+1));
pg.last.addEventListener("click",()=>goTo(Math.ceil(matches().length/PAGE)-1));
// initial language: query, hash, then saved choice, then browser
(function(){{
  let l=(new URLSearchParams(location.search).get("lang")||"").toLowerCase();
  if(!LANGS.includes(l))l=(location.hash||"").slice(1).toLowerCase();
  if(!LANGS.includes(l)){{try{{l=localStorage.getItem("servoom-locale")||""}}catch(e){{l=""}}}}
  if(!LANGS.includes(l)){{for(const b of (navigator.languages||[navigator.language||"en"])){{const p=b.slice(0,2).toLowerCase();if(LANGS.includes(p)){{l=p;break}}}}}}
  setLang(l||"en",false);
}})();
{load}
"""

FONTS = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Pixelify+Sans:wght@500;700&family=Noto+Sans:ital,wght@0,400;0,500;0,700;1,400&display=swap">'

if MODE == "artifact":
    page = f"""<title>{esc(T['en']['title'])}</title>
{FONTS}
<style>
{CSS}</style>

{body()}
<script>
{script()}</script>
"""
    (OUT / "like-block.html").write_text(page, encoding="utf-8")
    print("wrote", OUT / "like-block.html", round(len(page.encode()) / 1024), "KB", "accounts", len(accounts), "avatars", sum(1 for a in accounts if a[8]))
else:
    # 1. the sprite sheet, the accounts and the artwork pairs, for the stats repository
    assert STATS.is_dir(), f"servoom-stats checkout expected at {STATS}"
    dd = STATS / "data/bots"; (dd / "pairs").mkdir(parents=True, exist_ok=True)
    sheet = Image.new("RGBA", (SPRITE_COLS * PITCH + 1, SPRITE_ROWS * PITCH + 1), (0, 0, 0, 0))
    for i, a in enumerate(accounts):
        if not a[8]: continue                                                  # transparent cell: no avatar
        im = Image.open(AV / f"{a[0]}.png").convert("RGBA")
        if im.size != (16, 16): im = im.resize((16, 16), Image.NEAREST)   # a few avatars are 32, 64 or 128 px
        sheet.paste(im, (1 + (i % SPRITE_COLS) * PITCH, 1 + (i // SPRITE_COLS) * PITCH))
    sheet.save(dd / "avatars.webp", "WEBP", lossless=True, quality=100, method=6)   # half the size of a PNG
    for p in pairs:
        for key in ("bot_png", "orig_png"):
            shutil.copyfile(PAIRS_DIR / p[key], dd / "pairs" / p[key])
    (dd / "accounts.json").write_text(json.dumps({
        "_": "The 2,000 accounts of the like-block as their profiles read on 9 October 2026: "
             "[user id, nickname, level, score, likes given, fans, country, public artworks, has avatar (1/0)]. "
             "avatars.webp holds the avatars as 16-px cells on a 17-px pitch with a 1-px margin, %d per row, in this order "
             "(a transparent cell: no avatar). Built by servoom/requests/02-like-block-case/build_page.py." % SPRITE_COLS,
        "read": "2026-10-09", "cols": SPRITE_COLS, "rows": SPRITE_ROWS, "pitch": PITCH, "n": len(accounts),
        "rows": accounts}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # 2. the page
    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / "bots.css").write_text(CSS + SITE_CSS, encoding="utf-8")
    (SITE / "bots.js").write_text("// Generated by requests/02-like-block-case/build_page.py site; edit the strings in content_<lang>.json there.\n" + script(), encoding="utf-8")
    index = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(T['en']['title'])}</title>
<meta name="description" content="{esc(T['en']['lede'])}">
<link rel="icon" type="image/png" sizes="32x32" href="../favicon-32x32.png">
{FONTS}
<link rel="stylesheet" href="bots.css">
</head>
<body>
<!-- Generated by requests/02-like-block-case/build_page.py site; edit there, not here. -->
<header class="top">
  <a class="brand" href="../">servoom</a>
  <nav class="pillars">
    <a href="../download/" data-nav="nav_download">Download</a>
    <a href="../stats/" data-nav="nav_stats">Statistics</a>
    <a href="../artists/" data-nav="nav_artists">Artists</a>
    <a href="./" class="on" data-nav="nav_bots">Bots</a>
  </nav>
  <select id="lang" aria-label="Language">{langopts}</select>
</header>
{body()}
<footer class="site">
  <p data-nav="nav_unofficial">Unofficial. Not affiliated with Divoom.</p>
  <p><a href="https://github.com/fabkury/servoom">GitHub</a></p>
</footer>
<script src="bots.js"></script>
</body>
</html>
"""
    (SITE / "index.html").write_text(index, encoding="utf-8")
    print("wrote", SITE, "and", dd, "| sprite", sheet.size, "avatars", sum(a[8] for a in accounts), "| accounts", len(accounts),
          "| bots.js", round((SITE / "bots.js").stat().st_size / 1024), "KB")
