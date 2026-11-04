"""Build out/liking.html from out/numbers.json and out/charts.json (python build_page.py).

Self-contained page: inline CSS, inline SVG charts drawn here in Python, no third-party
assets, no libraries. Voice: servoom. Design tokens follow servoom.pages.dev/bots/.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
N = json.load(open(OUT / "numbers.json", encoding="utf8"))
C = json.load(open(OUT / "charts.json", encoding="utf8"))


def pct(x, d=0):
    return f"{x * 100:.{d}f}%"


def num(x):
    return f"{int(round(x)):,}"


# --------------------------------------------------------------------------- SVG helpers
W, H = 640, 300
ML, MR, MT, MB = 46, 16, 14, 34


def scale(lo, hi, a, b):
    return lambda v: a + (v - lo) / (hi - lo) * (b - a) if hi > lo else a


def nice_ticks(lo, hi, n=5):
    span = hi - lo
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    for m in (1, 2, 2.5, 5, 10):
        step = m * mag
        if span / step <= n:
            break
    t0 = math.ceil(lo / step) * step
    return [round(t0 + i * step, 10) for i in range(int((hi - t0) / step) + 1)]


def fmt_tick(v):
    if abs(v - round(v)) < 1e-9:
        return f"{int(round(v)):,}"
    return f"{v:g}"


def axes(x, y, xlo, xhi, ylo, yhi, xt=None, yt=None, xfmt=fmt_tick, yfmt=fmt_tick, xlabel="", ylabel=""):
    s = []
    for v in (yt if yt is not None else nice_ticks(ylo, yhi)):
        yy = y(v)
        s.append(f'<line class="grid" x1="{ML}" x2="{W - MR}" y1="{yy:.1f}" y2="{yy:.1f}"/>')
        s.append(f'<text class="tk" x="{ML - 6}" y="{yy + 3.5:.1f}" text-anchor="end">{yfmt(v)}</text>')
    for v in (xt if xt is not None else nice_ticks(xlo, xhi)):
        xx = x(v)
        s.append(f'<text class="tk" x="{xx:.1f}" y="{H - MB + 16}" text-anchor="middle">{xfmt(v)}</text>')
    s.append(f'<line class="ax" x1="{ML}" x2="{W - MR}" y1="{y(ylo):.1f}" y2="{y(ylo):.1f}"/>')
    if xlabel:
        s.append(f'<text class="al" x="{(ML + W - MR) / 2:.0f}" y="{H - 4}" text-anchor="middle">{xlabel}</text>')
    if ylabel:
        s.append(f'<text class="al" x="{ML}" y="{MT - 2}" text-anchor="start">{ylabel}</text>')
    return "\n".join(s)


def path(pts, cls):
    d = " ".join(f"{'M' if i == 0 else 'L'}{px:.1f},{py:.1f}" for i, (px, py) in enumerate(pts))
    return f'<path class="{cls}" d="{d}"/>'


def svg(body, title, h=H):
    return (f'<svg class="chart" viewBox="0 0 {W} {h}" role="img" aria-label="{title}" xmlns="http://www.w3.org/2000/svg">'
            f'{body}</svg>')


def dot(px, py, cls, tip, r=4):
    return f'<circle class="{cls}" cx="{px:.1f}" cy="{py:.1f}" r="{r}"><title>{tip}</title></circle>'


def bar(px, py, w, hgt, cls, tip):
    hgt = max(hgt, 0)
    rr = min(4, w / 2, hgt)
    return (f'<path class="{cls}" d="M{px:.1f},{py + hgt:.1f} v{-(hgt - rr):.1f} a{rr},{rr} 0 0 1 {rr},{-rr} h{w - 2 * rr:.1f} '
            f'a{rr},{rr} 0 0 1 {rr},{rr} v{hgt - rr:.1f} z"><title>{tip}</title></path>')


def hbar(px, py, wdt, hgt, cls, tip):
    wdt = max(wdt, 0)
    rr = min(4, hgt / 2, wdt)
    return (f'<path class="{cls}" d="M{px:.1f},{py:.1f} h{wdt - rr:.1f} a{rr},{rr} 0 0 1 {rr},{rr} v{hgt - 2 * rr:.1f} '
            f'a{rr},{rr} 0 0 1 {-rr},{rr} h{-(wdt - rr):.1f} z"><title>{tip}</title></path>')


LEGEND = '<div class="legend"><span><i class="sw b"></i>the block</span><span><i class="sw p"></i>everyone else</span></div>'


# --------------------------------------------------------------------------- charts
def chart_block_vs_human():
    rows = [x for x in C["block_vs_human_exact"] if x["h"] <= 40]
    x = scale(0, 40, ML, W - MR)
    y = scale(0, 45, H - MB, MT)
    s = [axes(x, y, 0, 40, 0, 45, xlabel="likes from people (artworks 1 to 6 months old)", ylabel="block likes, median per artwork")]
    s.append(path([(x(0), y(0)), (x(40), y(40))], "ref"))
    s.append(f'<text class="al" x="{x(30):.0f}" y="{y(24):.0f}" text-anchor="start">one for one</text>')
    for v in rows:
        s.append(dot(x(v["h"]), y(v["median"]), "db", f'{v["h"]} human likes: median {v["median"]:g} block likes ({v["n"]:,} artworks)'))
    return svg("\n".join(s), "Median block likes against human likes, artworks one to six months old")


def chart_multipliers():
    m = N["loglog"]["mult"]
    items = [("Master Pixel Artist", m["master"]), ("Featured artist", m["featured"]), ("Recommend pick", m["rec"]), ("NEW pick", m["new"]),
             ("Animation (vs still)", m["ani"]), ("Photo category", m["photo"]), ("32 px (vs 16)", m["px32"]), ("64 px (vs 16)", m["px64"]),
             ("128 px (vs 16)", m["px128"]), ("256 px (vs 16)", m["px256"])]
    h = MT + 24 * len(items) + MB
    x = scale(0.5, 1.5, 190, W - MR)
    s = []
    for v in (0.5, 0.75, 1.0, 1.25, 1.5):
        s.append(f'<line class="{"ax" if v == 1 else "grid"}" x1="{x(v):.1f}" x2="{x(v):.1f}" y1="{MT}" y2="{h - MB}"/>')
        s.append(f'<text class="tk" x="{x(v):.1f}" y="{h - MB + 16}" text-anchor="middle">{"×" + f"{v:g}"}</text>')
    for i, (k, v) in enumerate(items):
        yy = MT + i * 24 + 4
        s.append(f'<text class="lbl" x="182" y="{yy + 12}" text-anchor="end">{k}</text>')
        lo, hi = sorted((x(1.0), x(v)))
        s.append(hbar(lo, yy, hi - lo, 14, "fb", f"{k}: ×{v:g} block likes at equal human likes"))
        s.append(f'<text class="val" x="{(hi + 6) if v >= 1 else (lo - 6):.1f}" y="{yy + 11}" text-anchor="{"start" if v >= 1 else "end"}">×{v:g}</text>')
    s.append(f'<text class="al" x="{(190 + W - MR) / 2:.0f}" y="{h - 4}" text-anchor="middle">block likes relative to an ordinary 16-px, uncurated artwork with the same human likes</text>')
    return svg("\n".join(s), "Multipliers of block likes by artwork trait at equal human likes", h)


def chart_first_like():
    rows = C["first_like_cdf"]
    x = scale(0, 168, ML, W - MR)
    y = scale(0, 0.8, H - MB, MT)
    xt = [0, 24, 48, 72, 96, 120, 144, 168]
    s = [axes(x, y, 0, 168, 0, 0.8, xt=xt, yt=[0, .2, .4, .6, .8], xfmt=lambda v: f"{int(v // 24)} d" if v else "0", yfmt=lambda v: pct(v),
              xlabel="time since upload", ylabel="share of new uploads that have received a like")]
    pb = [(x(0), y(0))] + [(x(r["h"]), y(r["block"])) for r in rows]
    ph = [(x(0), y(0))] + [(x(r["h"]), y(r["human"])) for r in rows]
    s.append(path(ph, "lp"))
    s.append(path(pb, "lb"))
    for r in rows:
        s.append(dot(x(r["h"]), y(r["block"]), "db", f'{r["h"]} h: {pct(r["block"], 1)} of uploads have a block like', 3.5))
        s.append(dot(x(r["h"]), y(r["human"]), "dp", f'{r["h"]} h: {pct(r["human"], 1)} of uploads have a like from a person', 3.5))
    s.append(f'<text class="lab b" x="{x(100):.0f}" y="{y(0.735):.0f}">the block</text>')
    s.append(f'<text class="lab p" x="{x(100):.0f}" y="{y(0.60):.0f}">everyone else</text>')
    return svg("\n".join(s), "Share of uploads that have received their first like, by hours since upload")


def chart_rate_by_hour():
    rows = C["rate_by_hour"][:48]
    x = scale(0, 48, ML, W - MR)
    ymax = 0.28
    y = scale(0, ymax, H - MB, MT)
    s = [axes(x, y, 0, 48, 0, ymax, xt=[0, 6, 12, 18, 24, 30, 36, 42, 48], yt=[0, .05, .1, .15, .2, .25], yfmt=lambda v: f"{v:g}",
              xlabel="hours since upload", ylabel="likes per artwork per hour")]
    s.append(path([(x(r["h"] + .5), y(r["human"])) for r in rows], "lp"))
    s.append(path([(x(r["h"] + .5), y(r["block"])) for r in rows], "lb"))
    for r in rows:
        s.append(f'<rect class="hit" x="{x(r["h"]):.1f}" y="{MT}" width="{x(1) - x(0):.1f}" height="{H - MB - MT}"><title>hour {r["h"]}: {r["block"]:.3f} block likes, {r["human"]:.3f} human likes per artwork</title></rect>')
    s.append(f'<text class="lab p" x="{x(3):.0f}" y="{y(0.20):.0f}">everyone else</text>')
    s.append(f'<text class="lab b" x="{x(26):.0f}" y="{y(0.065):.0f}">the block</text>')
    return svg("\n".join(s), "Likes per artwork per hour over the first two days, block against everyone else")


def chart_share_over_life():
    items = [("first 6 h", N["rate"]["block_share_first6h"]), ("day 2", N["rate"]["block_share_day2"]), ("week 2", N["rate"]["block_share_week2"])]
    items += [(r["age"], r["block_share"]) for r in C["trickle_by_age"]]
    n = len(items)
    x = scale(0, n, ML, W - MR)
    y = scale(0, 0.8, H - MB, MT)
    s = [axes(x, y, 0, n, 0, 0.8, xt=[], yt=[0, .2, .4, .6, .8], yfmt=lambda v: pct(v), ylabel="share of new likes that come from the block")]
    bw = (x(1) - x(0)) * 0.6
    for i, (k, v) in enumerate(items):
        px = x(i) + (x(1) - x(0) - bw) / 2
        s.append(bar(px, y(v), bw, y(0) - y(v), "fb", f"{k}: {pct(v)} of likes from the block"))
        s.append(f'<text class="tk" x="{x(i + .5):.1f}" y="{H - MB + 16}" text-anchor="middle">{k}</text>')
        s.append(f'<text class="val" x="{x(i + .5):.1f}" y="{y(v) - 5:.1f}" text-anchor="middle">{pct(v)}</text>')
    s.append(f'<line class="ax" x1="{x(3):.1f}" x2="{x(3):.1f}" y1="{MT}" y2="{H - MB}" stroke-dasharray="3 3"/>')
    s.append(f'<text class="al" x="{x(1.5):.0f}" y="{H - 4}" text-anchor="middle">artwork age when liked (hourly reads)</text>')
    s.append(f'<text class="al" x="{x(6.5):.0f}" y="{H - 4}" text-anchor="middle">artwork age when liked (two-daily reads of older artworks)</text>')
    return svg("\n".join(s), "Share of likes coming from the block, by the age of the artwork when the like arrives")


def chart_hour_of_day():
    rows = C["hour_of_day"]
    x = scale(0, 24, ML, W - MR)
    ymax = 140
    y = scale(0, ymax, H - MB, MT)
    s = [axes(x, y, 0, 24, 0, ymax, xt=[0, 4, 8, 12, 16, 20, 24], yt=[0, 40, 80, 120], xfmt=lambda v: f"{int(v):02d}:00",
              xlabel="hour of day, UTC (add 8 for Beijing, subtract 4 for New York)", ylabel="likes per hour, average over 5 Oct to 3 Nov 2026")]
    s.append(path([(x(r["h"] + .5), y(r["human"])) for r in rows], "lp"))
    s.append(path([(x(r["h"] + .5), y(r["block"])) for r in rows], "lb"))
    for r in rows:
        s.append(f'<rect class="hit" x="{x(r["h"]):.1f}" y="{MT}" width="{x(1) - x(0):.1f}" height="{H - MB - MT}"><title>{r["h"]:02d}:00 UTC: {r["block"]:g} block likes, {r["human"]:g} human likes per hour</title></rect>')
    s.append(f'<text class="lab b" x="{x(13):.0f}" y="{y(42):.0f}">the block</text>')
    s.append(f'<text class="lab p" x="{x(15):.0f}" y="{y(128):.0f}">everyone else</text>')
    return svg("\n".join(s), "Likes per hour by hour of day, block against everyone else")


def chart_list_position():
    rows = C["list_position"]
    x = scale(0, 10, ML, W - MR)
    y = scale(0, 0.8, H - MB, MT)
    s = [axes(x, y, 0, 10, 0, 0.8, xt=[], yt=[0, .2, .4, .6, .8], yfmt=lambda v: pct(v), ylabel="share of likes in that tenth that come from the block")]
    bw = (x(1) - x(0)) * 0.6
    for r in rows:
        i = 9 - r["decile"]          # oldest on the left
        px = x(i) + (x(1) - x(0) - bw) / 2
        s.append(bar(px, y(r["block_share"]), bw, y(0) - y(r["block_share"]), "fb", f"tenth {i + 1} of the list (1 = oldest likes): {pct(r['block_share'])} from the block"))
        s.append(f'<text class="val" x="{x(i + .5):.1f}" y="{y(r["block_share"]) - 5:.1f}" text-anchor="middle">{pct(r["block_share"])}</text>')
    s.append(f'<text class="tk" x="{x(0.5):.0f}" y="{H - MB + 16}" text-anchor="middle">oldest likes</text>')
    s.append(f'<text class="tk" x="{x(9.5):.0f}" y="{H - MB + 16}" text-anchor="middle">newest likes</text>')
    s.append(f'<text class="al" x="{(ML + W - MR) / 2:.0f}" y="{H - 4}" text-anchor="middle">each artwork\'s like list split into ten equal parts, oldest to newest (artworks with 10+ likes, uploaded in the past year)</text>')
    return svg("\n".join(s), "Share of block likes along the like list of an artwork, from its oldest likes to its newest")


def chart_uploaders():
    reg = C["regular_uploaders"]
    mas = C["masters"]
    lx = lambda v: math.log10(v + 1)
    x = scale(0, lx(400), ML, W - MR)
    y = scale(0, lx(160), H - MB, MT)
    xt = [0, 1, 3, 10, 30, 100, 300]
    yt = [0, 1, 3, 10, 30, 100]
    s = [axes(x, y, 0, lx(400), 0, lx(160), xt=[lx(v) for v in xt], yt=[lx(v) for v in yt], xfmt=lambda v: fmt_tick(round(10 ** v - 1)),
              yfmt=lambda v: fmt_tick(round(10 ** v - 1)), xlabel="likes from people per artwork (uploader average)", ylabel="block likes per artwork (uploader average)")]
    s.append(path([(x(0), y(0)), (x(lx(160)), y(lx(160)))], "ref"))
    for u in reg:
        s.append(dot(x(lx(u["mean_human"])), y(lx(u["mean_block"])), "dr", f'an ordinary uploader: {u["mean_human"]:g} human and {u["mean_block"]:g} block likes per artwork', 2.5))
    for u in mas:
        s.append(dot(x(lx(u["mean_human"])), y(lx(u["mean_block"])), "dm", f'a Master Pixel Artist (level {u["level"]}, {u["arts"]} artworks): {u["mean_human"]:g} human and {u["mean_block"]:g} block likes per artwork', 5))
    s.append(f'<text class="al" x="{x(lx(120)):.0f}" y="{y(lx(150)):.0f}" text-anchor="end">one for one</text>')
    return svg("\n".join(s), "Uploaders: block likes per artwork against human likes per artwork, Masters marked")


def chart_accounts():
    rows = C["account_dist"]
    lo, hi = 400, 560
    bins = list(range(lo, hi + 1, 10))
    counts = [sum(r["accounts"] for r in rows if b <= r["likes"] < b + 10) for b in bins[:-1]]
    x = scale(lo, hi, ML, W - MR)
    y = scale(0, max(counts) * 1.1, H - MB, MT)
    s = [axes(x, y, lo, hi, 0, max(counts) * 1.1, xt=bins[::2], xlabel="likes given in the year by one block account", ylabel="number of accounts")]
    bw = x(10) - x(0) - 2
    for b, c in zip(bins[:-1], counts):
        s.append(bar(x(b) + 1, y(c), bw, y(0) - y(c), "fb", f"{b} to {b + 9} likes: {c} accounts"))
    return svg("\n".join(s), "How many likes each of the 2,000 accounts gave to the year's uploads")


# --------------------------------------------------------------------------- tables
def table_tiers():
    t = N["tiers"]
    rows = [("Master Pixel Artists", t["master"]), ("Featured artists", t["featured"]), ("Everyone else", t["regular"])]
    out = ['<div class="tw"><table><thead><tr><th>Uploader</th><th>Artworks</th><th>Likes from people, per artwork</th><th>Block likes, per artwork</th><th>Share of likes from the block</th><th>Artworks with any block like</th><th>First block like arrives after</th></tr></thead><tbody>']
    fl = N["first_like_by_tier"]
    for name, d in rows:
        key = {"Master Pixel Artists": "master", "Featured artists": "featured", "Everyone else": "regular"}[name]
        out.append(f'<tr><td>{name}</td><td>{num(d["artworks"])} by {num(d["uploaders"])}</td><td>{d["mean_human"]:g} (median {d["median_human"]:g})</td>'
                   f'<td>{d["mean_block"]:g} (median {d["median_block"]:g})</td><td>{pct(d["block_share"])}</td><td>{pct(d["reach_block"])}</td><td>{fl[key]["median_h"]:g} h (people: {fl[key]["human_median_h"]:g} h)</td></tr>')
    out.append("</tbody></table></div>")
    return "\n".join(out)


def table_matched():
    bands = ["6-10", "11-20", "21-50", "51-100", "100+"]
    d = {(r["tier"], r["human"]): r for r in C["tier_by_human"]}
    out = ['<div class="tw"><table><thead><tr><th>Likes from people</th><th>Master Pixel Artists</th><th>Featured artists</th><th>Everyone else</th></tr></thead><tbody>']
    for b in bands:
        cells = []
        for tr in ("master", "featured", "regular"):
            r = d.get((tr, b))
            cells.append(f'{r["mean_block"]:g} <span class="n">({r["n"]:,})</span>' if r else "<span class=\"n\">too few</span>")
        out.append(f"<tr><td>{b}</td><td>{cells[0]}</td><td>{cells[1]}</td><td>{cells[2]}</td></tr>")
    out.append("</tbody></table></div>")
    return "\n".join(out)


def table_traits():
    rows = []
    for key, label in (("by_size", "Canvas"), ("by_type", "Type"), ("by_curation", "Curation"), ("by_cls", "Category")):
        for r in C[key]:
            if key == "by_cls" and r["n"] < 1000:
                continue
            name = r["key"] + (" px" if key == "by_size" and r["key"].isdigit() else "")
            rows.append((label, name, r))
    out = ['<div class="tw"><table><thead><tr><th></th><th>Artworks</th><th>Likes from people, per artwork</th><th>Block likes, per artwork</th><th>Block likes per human like</th></tr></thead><tbody>']
    last = None
    for label, name, r in rows:
        grp = f'<span class="grp">{label}</span> ' if label != last else ""
        last = label
        out.append(f'<tr><td>{grp}{name}</td><td>{r["n"]:,}</td><td>{r["mean_human"]:g}</td><td>{r["mean_block"]:g}</td><td>{r["ratio"]:g}</td></tr>')
    out.append("</tbody></table></div>")
    return "\n".join(out)


# --------------------------------------------------------------------------- page
B, O, FL, T, E, R, A, CK, G = N["bf"], N["old"], N["first_like"], N["tiers"], N["ev"], N["rate"], N["accounts"], N["clock"], N["loglog"]
TR = N["trickle"]
M = T["matched"]
from scipy.stats import poisson  # noqa: E402
PLO, PHI = int(poisson.ppf(0.025, O["mean_block"])), int(poisson.ppf(0.975, O["mean_block"]))
FT = N["first_like_by_tier"]
bh = {r["human"]: r for r in C["block_by_human"]}
eh = {r["human_6h"]: r for r in C["early_human_later_block"]}

CSS = """/* Layout: one reading column, servoom house tokens; two series colors only (block orange, people blue); charts are inline SVG. */
:root {
  --bg:#f3f4f6; --surface:#ffffff; --fg:#161a20; --fg2:#4a5260; --muted:#737b88; --line:#dadfe6;
  --block:#e2641c; --block-bg:#fdeee4; --people:#2466b8; --people-bg:#e6eef9; --grid:#e6e9ee;
  --display:"Pixelify Sans","Courier New",monospace;
  --body:"Noto Sans","Segoe UI","Helvetica Neue",Arial,sans-serif;
  --mono:ui-monospace,"Cascadia Mono",Consolas,"Noto Sans Mono",monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg:#12151a; --surface:#1a1e25; --fg:#eceef2; --fg2:#b5bcc8; --muted:#8a93a1; --line:#2c323c;
  --block:#d9641f; --block-bg:#3a2415; --people:#4a8adb; --people-bg:#1b2a40; --grid:#242a33; color-scheme:dark } }
:root[data-theme="dark"] {
  --bg:#12151a; --surface:#1a1e25; --fg:#eceef2; --fg2:#b5bcc8; --muted:#8a93a1; --line:#2c323c;
  --block:#d9641f; --block-bg:#3a2415; --people:#4a8adb; --people-bg:#1b2a40; --grid:#242a33; color-scheme:dark }
* { box-sizing:border-box }
body { margin:0; background:var(--bg); color:var(--fg); font-family:var(--body); font-size:16px; line-height:1.6 }
.wrap { max-width:820px; margin:0 auto; padding-left:max(16px, env(safe-area-inset-left, 0px)); padding-right:max(16px, env(safe-area-inset-right, 0px)); padding-block:28px 72px; display:flex; flex-direction:column; gap:44px }
section, header.lead { display:flex; flex-direction:column; gap:14px; min-width:0 }
h1,h2,h3 { margin:0; line-height:1.2; text-wrap:balance }
h1 { font-size:clamp(1.9rem,5.5vw,2.8rem); font-weight:700; letter-spacing:-.01em }
h2 { font-size:1.45rem; font-weight:700 }
h3 { font-size:1.05rem; font-weight:700 }
p, li { margin:0; max-width:68ch }
ul { margin:0; padding-left:1.2em; display:flex; flex-direction:column; gap:8px }
.eyebrow { font-family:var(--display); font-size:.9rem; letter-spacing:.06em; text-transform:uppercase; color:var(--block) }
.lede { font-size:1.15rem; color:var(--fg2); max-width:62ch }
.meta { font-size:.85rem; color:var(--muted) }
.meta a, p a { color:inherit }
.verdict { background:var(--surface); border-left:4px solid var(--block); padding:16px 20px; display:flex; flex-direction:column; gap:8px; border-radius:0 6px 6px 0 }
.verdict .vl { font-family:var(--display); font-size:.9rem; letter-spacing:.06em; text-transform:uppercase; color:var(--block) }
.tiles { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px }
.tile { background:var(--surface); padding:14px 16px; border-radius:6px; display:flex; flex-direction:column; gap:4px; min-width:0 }
.tile .v { font-family:var(--display); font-size:2rem; line-height:1.1; color:var(--block) }
.tile .v.p { color:var(--people) }
.tile .l { font-weight:500; font-size:.92rem }
.tile .s { font-size:.8rem; color:var(--muted) }
figure { margin:0; background:var(--surface); padding:14px 16px 12px; border-radius:6px; display:flex; flex-direction:column; gap:8px; min-width:0 }
figcaption { font-size:.82rem; color:var(--muted); max-width:75ch }
.ftitle { font-weight:600; font-size:.95rem }
.chart { width:100%; height:auto; display:block; font-family:var(--body) }
.chart .grid { stroke:var(--grid); stroke-width:1 }
.chart .ax { stroke:var(--line); stroke-width:1 }
.chart .tk { font-size:11px; fill:var(--muted) }
.chart .al { font-size:11px; fill:var(--muted) }
.chart .lbl { font-size:12px; fill:var(--fg2) }
.chart .val { font-size:11px; fill:var(--fg2) }
.chart .lab { font-size:12px; font-weight:600 }
.chart .lab.b { fill:var(--block) } .chart .lab.p { fill:var(--people) }
.chart .lb { fill:none; stroke:var(--block); stroke-width:2; stroke-linejoin:round; stroke-linecap:round }
.chart .lp { fill:none; stroke:var(--people); stroke-width:2; stroke-linejoin:round; stroke-linecap:round }
.chart .ref { fill:none; stroke:var(--muted); stroke-width:1; stroke-dasharray:4 4 }
.chart .db { fill:var(--block); stroke:var(--surface); stroke-width:1.5 }
.chart .dp { fill:var(--people); stroke:var(--surface); stroke-width:1.5 }
.chart .dr { fill:var(--people); opacity:.45 }
.chart .dm { fill:var(--block); stroke:var(--surface); stroke-width:1.5 }
.chart .fb { fill:var(--block) }
.chart .hit { fill:transparent }
.chart .hit:hover { fill:var(--grid); opacity:.5 }
.chart circle:hover, .chart path.fb:hover { opacity:.75 }
.legend { display:flex; flex-wrap:wrap; gap:6px 18px; font-size:.82rem; color:var(--fg2) }
.sw { display:inline-block; width:12px; height:12px; border-radius:3px; margin-right:6px; vertical-align:-1px }
.sw.b { background:var(--block) } .sw.p { background:var(--people) }
.tw { overflow-x:auto; background:var(--surface); border-radius:6px }
table { border-collapse:collapse; width:100%; font-size:.86rem; font-variant-numeric:tabular-nums }
th, td { text-align:right; padding:8px 10px; border-bottom:1px solid var(--line); white-space:nowrap }
th:first-child, td:first-child { text-align:left }
th { font-weight:600; color:var(--muted); font-size:.78rem; text-transform:uppercase; letter-spacing:.04em }
tr:last-child td { border-bottom:0 }
td .n { color:var(--muted); font-size:.78rem }
td .grp { display:inline-block; min-width:5.2em; color:var(--muted); font-size:.78rem; text-transform:uppercase; letter-spacing:.04em }
.key { display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:12px }
.key > div { background:var(--surface); padding:14px; border-radius:6px; display:flex; flex-direction:column; gap:6px; font-size:.92rem; color:var(--fg2); min-width:0 }
.key b { color:var(--fg) }
.key .k { font-family:var(--display); font-size:.8rem; letter-spacing:.05em; text-transform:uppercase; color:var(--block) }
details { background:var(--surface); border-radius:6px; padding:10px 16px }
summary { cursor:pointer; font-weight:600 }
details > *:not(summary) { margin-top:10px }
footer { font-size:.85rem; color:var(--muted); border-top:1px solid var(--line); padding-top:16px }
@media (prefers-reduced-motion: no-preference) { .chart circle, .chart path.fb { transition:opacity .15s } }
"""

body = f"""
<title>How the Like Block Chooses</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Pixelify+Sans:wght@500;700&family=Noto+Sans:ital,wght@0,400;0,500;0,700;1,400&display=swap">
<style>{CSS}</style>
<div class="wrap">

<header class="lead">
  <div class="eyebrow">servoom · report</div>
  <h1>How the Like Block Chooses</h1>
  <p class="lede">The 2,000 automated accounts that like Divoom artworks do not pick at random, and they do not have taste. They copy the crowd: an artwork gets about as many likes from the block as it gets from people, a day or so later, and the topping-up never stops.</p>
  <p class="meta">A follow-up to <a href="https://servoom.pages.dev/bots/">Who Is Liking Your Divoom Art?</a>, which identified the block. This page is only about what the block likes and when. Data read from the public Divoom gallery between October 2025 and 3 November 2026; details at the end.</p>
</header>

<section>
  <div class="verdict">
    <div class="vl">In short</div>
    <p><b>The block mirrors people.</b> Count the likes an artwork received from real accounts and you know, within a few, how many it received from the block. Human likes alone explain {pct(G["r2_human_only"])} of the variation in block likes between artworks; the canvas size, the category, whether it is an animation, whether Divoom curated it and who posted it together add {pct(G["r2"] - G["r2_human_only"], 1)}.</p>
    <p><b>Masters are not favoured.</b> A Master Pixel Artist's artwork gets about ten times the block likes of an ordinary one, but only because it gets more than twenty times the human likes. At equal human popularity a Master gets {M["master_mean"]:g} block likes and anyone else gets {M["regular_at_same_popularity"]:g}.</p>
    <p><b>People first, block second.</b> On {pct(FL["human_first_share"])} of new uploads the first like from a person arrives before the first from the block. The block's first like comes at a median {FL["block_hours_q"]["0.5"]:g} hours after upload, people's at {FL["human_hours_q"]["0.5"]:g}. After the first month the block supplies two of every three new likes, on artworks of any age up to eight years.</p>
  </div>
</section>

<section>
  <div class="tiles">
    <div class="tile"><div class="v">{B["block_likes"] / 1e6:.2f}M</div><div class="l">block likes on one year of uploads</div><div class="s">{pct(B["block_share"])} of the {B["likes"] / 1e6:.2f}M likes on {num(B["artworks"])} public artworks uploaded 5 Oct 2025 to 5 Oct 2026</div></div>
    <div class="tile"><div class="v">{N["corr"]["mature"]["block_vs_human"]:.2f}</div><div class="l">rank correlation, block likes vs human likes</div><div class="s">per artwork, {num(N["corr"]["mature"]["n"])} artworks one to six months old (1.00 would be a perfect match)</div></div>
    <div class="tile"><div class="v p">{FL["human_hours_q"]["0.5"]:g} h</div><div class="l">median wait for the first human like</div><div class="s">new uploads, October 2026</div></div>
    <div class="tile"><div class="v">{FL["block_hours_q"]["0.5"]:g} h</div><div class="l">median wait for the first block like</div><div class="s">same uploads; {pct(FL["block_within_1h"], 1)} of them got one within the first hour</div></div>
  </div>
</section>

<section>
  <h2>1. The block likes what people like</h2>
  <p>Take every public artwork uploaded between April and September 2026 and read its full like list: {num(O["n"])} artworks, old enough that the first burst of attention is over. Split each list into likes from the 2,000 block accounts and likes from everyone else. The two numbers move together almost exactly. An artwork with one human like has a median of {bh["1-2"]["median_block"]:g} block likes; with 10, about {next(r for r in C["block_vs_human_exact"] if r["h"] == 10)["median"]:g}; with 20, about {next(r for r in C["block_vs_human_exact"] if r["h"] == 20)["median"]:g}; with 40, about {next(r for r in C["block_vs_human_exact"] if r["h"] == 40)["median"]:g}.</p>
  <figure>
    <div class="ftitle">One block like for every human like, give or take</div>
    {chart_block_vs_human()}
    <figcaption>Median number of block likes on artworks with exactly that many likes from people. Dashed line: equal counts. Artworks uploaded 5 April to 6 September 2026, like lists read 6 October 2026.</figcaption>
  </figure>
  <p>The match is tight at the artwork level, not just on average. Within the group of artworks uploaded in a single week, the rank correlation between block likes and human likes is {N["corr"]["one_week_cohort"]["block_vs_human"]:.2f}. A rule of thumb for the whole range: block likes rise as human likes to the power {G["alpha"]:g}, almost straight proportionality, so the very popular get a little less than one-for-one (an artwork with 100 or more human likes has a median of {bh["100+"]["median_block"]:g} block likes against a mean of {bh["100+"]["mean_human"]:g} from people) and the barely noticed get a little more.</p>
  <p>The one place the block is shy is the artwork nobody liked. Of the {num(bh["0"]["n"])} artworks with no human like at all, {pct(bh["0"]["reach_block"])} received a block like, and the average is {bh["0"]["mean_block"]:g}. As soon as one person has liked an artwork, the block always follows: {pct(bh["1-2"]["reach_block"])} of artworks with one or two human likes have at least one block like.</p>
  <p>This is not what random liking looks like. If the block had spread its {num(O["mean_block"] * O["n"])} likes on these artworks by chance, 95% of artworks would have between {PLO} and {PHI} of them. Instead {pct(O["share_0"])} got none and {pct(O["share_ge30"])} got 30 or more, up to {O["max_block"]}.</p>
</section>

<section>
  <h2>2. Nothing else matters much</h2>
  <p>Big canvases, animations, Nature versus Photo, uploads Divoom put in the NEW or Recommend feeds, uploaders at level 30: every one of these receives a different number of block likes, and in every case the difference is the difference in human likes. Holding human likes fixed, a statistical model finds only small adjustments, all under a quarter either way.</p>
  <figure>
    <div class="ftitle">What changes the count of block likes once human likes are held equal</div>
    {chart_multipliers()}
    <figcaption>From a model of block likes on the {num(O["n"])} mature artworks: multiplier applied to the block likes of an uncurated 16-pixel still by an ordinary uploader with the same number of human likes. ×1 means no effect. Human likes alone explain {pct(G["r2_human_only"])} of the variation; everything here together adds {pct(G["r2"] - G["r2_human_only"], 1)}.</figcaption>
  </figure>
  <p>The raw numbers tell the same story from the other side. Photos (a third of all uploads) get {next(r for r in C["by_cls"] if r["key"] == "Photo")["mean_block"]:g} block likes each and Nature artworks {next(r for r in C["by_cls"] if r["key"] == "Nature")["mean_block"]:g}, but Nature artworks also get eight times the human likes. Recommend picks get {next(r for r in C["by_curation"] if r["key"] == "Recommend pick")["mean_block"]:g} block likes, ten times an uncurated upload, and {next(r for r in C["by_curation"] if r["key"] == "Recommend pick")["mean_human"]:g} human likes, twenty-four times. Because the block grows slightly slower than one-for-one, its share of an artwork's likes falls as the artwork gets popular: it is {pct(next(r for r in C["by_curation"] if r["key"] == "not curated")["block_share"])} of the likes on an uncurated upload and {pct(next(r for r in C["by_curation"] if r["key"] == "Recommend pick")["block_share"])} on a Recommend pick.</p>
  <details>
    <summary>Block likes by canvas, type, curation and category</summary>
    {table_traits()}
    <p class="meta">Artworks uploaded 5 April to 6 September 2026, like lists read 6 October 2026. Categories with fewer than 1,000 artworks left out.</p>
  </details>
</section>

<section>
  <h2>3. Master Pixel Artists against everyone else</h2>
  <p>Divoom gives a badge to a small group of uploaders, the Master Pixel Artists ({N["tiers_def"]["masters_known"]} accounts carry it in our data), and features a wider circle of about {num(N["tiers_def"]["featured_no_badge"] + N["tiers_def"]["masters_known"])} artists in its Expert list and Recommend feed. The question we were asked: does the block treat them differently?</p>
  <p>In absolute terms, yes, enormously. A Master's artwork gets {T["master"]["mean_block"]:g} block likes on average and an ordinary uploader's gets {T["regular"]["mean_block"]:g}. But a Master's artwork also gets {T["master"]["mean_human"]:g} likes from people against {T["regular"]["mean_human"]:g}. Line the artworks up by human likes and the badge disappears:</p>
  {table_matched()}
  <p class="meta">Average block likes per artwork, by the artwork's count of human likes and the uploader's standing. In brackets, the number of artworks. Mature artworks, uploaded April to September 2026.</p>
  <p>Weighting the ordinary uploaders to the Masters' mix of popularity, a Master gets {M["master_mean"]:g} block likes per artwork and an ordinary uploader with the same human likes gets {M["regular_at_same_popularity"]:g}. The model in section 2 puts the badge at ×{G["mult"]["master"]:g}: if anything, Masters receive slightly fewer block likes than their popularity would predict, because the block's response flattens at the top. The block has no VIP list.</p>
  <figure>
    <div class="ftitle">Every uploader with five or more mature artworks</div>
    {chart_uploaders()}
    <figcaption>One dot per uploader: the average human likes and average block likes on their artworks uploaded April to September 2026. Orange, the {N["masters_spread"]["uploaders"]} Master Pixel Artists with five or more such artworks; blue, the {num(N["regular_uploaders_spread"]["uploaders"])} ordinary uploaders with five or more. Both axes are logarithmic. Dashed line: equal counts.</figcaption>
  </figure>
  <p>Where Masters do differ is speed, and again it is the crowd's speed. A new upload by a Master gets its first human like after a median {FT["master"]["human_median_h"]:g} hours and its first block like after {FT["master"]["median_h"]:g}; an ordinary upload waits {FT["regular"]["human_median_h"]:g} hours for a person and {FT["regular"]["median_h"]:g} for the block. The block reaches {pct(FT["master"]["reached_7d"])} of Masters' uploads within a week and {pct(FT["regular"]["reached_7d"])} of everyone else's, which is almost exactly the share of each that any person liked ({pct(FT["master"]["human_reached_7d"])} and {pct(FT["regular"]["human_reached_7d"])}).</p>
  {table_tiers()}
  <p class="meta">"Featured artists" are the accounts servoom already names on its statistics pages: on Divoom's Expert list, badge holders, or picked for the Recommend feed three or more times in the year, minus the badge holders. Divoom's Expert list alone is not kept in our data, so this middle tier is a little wider than the list.</p>
  <p>One consequence is worth spelling out. Because the block gives little-liked artworks slightly more than one-for-one and popular ones slightly less, it compresses the gap between the top and the rest. The block is {pct(T["regular"]["block_share"])} of the likes on an ordinary uploader's artwork and {pct(T["master"]["block_share"])} of the likes on a Master's. Masters post {pct(T["master"]["share_uploads"])} of the artworks, receive {pct(T["master"]["share_human_likes"])} of the human likes, and {pct(T["master"]["share_block_likes"])} of the block's.</p>
</section>

<section>
  <h2>4. A day late, then forever</h2>
  <p>From 5 October to 3 November 2026 servoom read the like lists of new uploads every hour, which dates each like to within an hour. The block almost never likes a fresh upload: {pct(FL["block_within_1h"], 1)} of uploads had a block like within the first hour, against {pct(FL["human_within_1h"])} with a like from a person. By six hours it is {pct(FL["block_within_6h"])} against {pct(FL["human_within_6h"])}; by a day, {pct(FL["block_within_24h"])} against {pct(FL["human_within_24h"])}. Only after two days has the block caught up.</p>
  <figure>
    <div class="ftitle">Who gets there first</div>
    {LEGEND}
    {chart_first_like()}
    <figcaption>Share of the {num(FL["artworks_7d"])} public uploads of 5 to 27 October 2026 that had received at least one like from the block, and from anyone else, by time since upload. Hourly reads of the like lists.</figcaption>
  </figure>
  <p>The hourly rate shows the shape of the delay. People like an upload most in its first hour and less every hour after. The block starts near zero, climbs through the first day, peaks around the end of the first day and the start of the second, and then declines in step with the human rate, a little behind it. On {pct(FL["human_first_share"])} of uploads that got both kinds of like, the person came first.</p>
  <figure>
    <div class="ftitle">Likes per hour over an upload's first two days</div>
    {LEGEND}
    {chart_rate_by_hour()}
    <figcaption>Average likes received per public upload in each hour since upload, uploads of October 2026. The block's curve is the lagged shadow of the human one.</figcaption>
  </figure>
  <p>Early attention from people predicts later attention from the block. Among uploads that no person liked in their first six hours, {pct(eh["0"]["reach_block"])} got a block like in the following three days, {eh["0"]["block_6_72h"]:g} on average. One human like in the first six hours lifts that to {pct(eh["1"]["reach_block"])} and {eh["1"]["block_6_72h"]:g}; five to eight human likes, to {pct(eh["5-8"]["reach_block"])} and {eh["5-8"]["block_6_72h"]:g}. The reverse is much weaker: early block likes barely predict later human likes (rank correlation {N["early"]["corr_b6_h72"]:.2f}, against {N["early"]["corr_h6_b72"]:.2f} the other way round).</p>
  <p>The block is not reacting minute by minute, though. Hour by hour, a block like is somewhat more likely in the hour after a person liked ({pct(N["lag"]["p_block_given_human_prev"])} against {pct(N["lag"]["p_block_given_no_human_prev"])}), but block likes mostly land in hours when nobody is looking: more often than not the view counter does not move in the hour a block like arrives. The block behaves like a scheduler that returns to each artwork now and then and adds likes in proportion to the attention it has gathered so far, {N["per_hour"]["block_mean"]:g} at a time on average ({pct(N["per_hour"]["block_share_1"])} of visits add exactly one), with a median {N["gaps"]["block_median_h"]:g} hours between visits to the same artwork in its first week.</p>
  <figure>
    <div class="ftitle">The block's share of new likes grows with the artwork's age</div>
    {chart_share_over_life()}
    <figcaption>Left of the dashed line: likes on October 2026 uploads, dated to the hour. Right: likes added between two-daily reads to artworks older than a month, {num(TR["likes"])} likes on {num(TR["artworks"])} artworks, October 2026. Age is the artwork's age at the moment of the like.</figcaption>
  </figure>
  <p>After the first week the pattern settles and never changes. Of the likes added in October 2026 to artworks older than a month, {pct(TR["block_share"])} came from the block, and the share is the same for an artwork from last spring and for one from 2018: between {pct(min(r["block_share"] for r in C["trickle_by_age"]))} and {pct(max(r["block_share"] for r in C["trickle_by_age"]))} in every age band. The year-long like lists show the same thing read backwards: in an artwork's like list the oldest likes are mostly from people and the newest mostly from the block.</p>
  <figure>
    <div class="ftitle">Along the like list, people at the start and the block at the end</div>
    {chart_list_position()}
    <figcaption>Each artwork's like list (newest first in the app, shown here oldest first) cut into ten equal parts; the bar is the share of likes in that part that come from block accounts. {num(B["artworks_liked"])} artworks uploaded in the year to 5 October 2026 with ten or more likes. The very first like on an artwork is from a block account {pct(N["first_likes"]["first_like_block"])} of the time; the most recent one, {pct(N["first_likes"]["newest_like_block"])}.</figcaption>
  </figure>
</section>

<section>
  <h2>5. Around the clock, no favourite hour</h2>
  <p>The block runs every hour of every day. Its busiest hour of the day delivers {CK["block_max_over_min"]:g} times the likes of its quietest, which is about the same unevenness as people show ({CK["human_max_over_min"]:g} times). Its day has a different shape from the human day, though: the block's peak is around {CK["block_hour_max"]:02d}:00 UTC, which is morning in China, and its trough around {CK["block_hour_min"]:02d}:00 UTC, when the human gallery is at its busiest. Across the week the block is flat; Saturday is its quietest day and the busiest for people.</p>
  <figure>
    <div class="ftitle">Likes per hour of the day</div>
    {LEGEND}
    {chart_hour_of_day()}
    <figcaption>Average number of likes dated to each hour of the day, on the recent uploads servoom read hourly, 5 October to 3 November 2026 ({num(CK["sharp_likes"])} likes, {num(CK["sharp_block"])} from the block). Hours with missed reads are averaged over the reads that did happen.</figcaption>
  </figure>
  <p>Posting time does not matter either: artworks uploaded at any hour of the day end up with between 0.9 and 1.2 block likes per human like.</p>
</section>

<section>
  <h2>6. Which of the 2,000 presses the button</h2>
  <p>Any of them, with equal probability. Over the year's uploads each block account gave between {A["min"]} and {A["max"]} likes, {A["mean"]:g} on average, and the spread between accounts ({pct(A["cv"], 1)} of the mean) is exactly what a coin toss over 2,000 names would give ({pct(A["poisson_cv"], 1)}). The 20 busiest accounts gave {pct(A["top20_share"], 1)} of the likes, which is their fair share. Two block likes in a row on the same artwork come from unrelated ids, and an account is no more likely to return to an uploader it already liked than chance predicts ({pct(A["share_repeat_uploader"], 1)} of likes go to an uploader the same account had liked before; random assignment gives {pct(A["share_repeat_uploader_if_random"], 1)}). Compare people: half of the {num(A["human_likers"])} human accounts gave two likes or fewer in the year, and the busiest 1% gave {pct(A["human_top1pct_share"])} of all human likes.</p>
  <figure>
    <div class="ftitle">Likes given per block account over one year of uploads</div>
    {chart_accounts()}
    <figcaption>Each account's count of likes on artworks uploaded 5 October 2025 to 5 October 2026, in bins of ten. The bell is the one chance alone produces.</figcaption>
  </figure>
</section>

<section>
  <h2>What it means for your like count</h2>
  <div class="key">
    <div><div class="k">The rule of thumb</div><p>Halve it. For an artwork a month old or more, roughly one like in two is from the block, and the block's count tracks the human count. An artwork with 20 likes probably has about 10 admirers.</p></div>
    <div><div class="k">The first hours are honest</div><p>Likes in the first six hours after you post are {pct(1 - R["block_share_first6h"])} from people. Whatever you see in that window is real attention.</p></div>
    <div><div class="k">Old artworks</div><p>A like that arrives on something you posted months or years ago is from the block two times out of three, whoever you are.</p></div>
    <div><div class="k">Nobody is boosted</div><p>The block does not promote Masters, Recommend picks, big canvases or any category. It amplifies whatever people already liked, slightly flattening the gap between the popular and the rest.</p></div>
  </div>
  <p>What the block does not do is also telling. It never comments, it never follows, it does not register a view, and it does not lead: the person comes first and the block follows. Whoever runs it built a machine that makes the gallery look about twice as appreciative as it is, without changing who is appreciated.</p>
</section>

<section>
  <h2>Method and limits</h2>
  <ul>
    <li><b>The block.</b> The 2,000 accounts are the even user ids between 400971852 and 400975850, as established in <a href="https://servoom.pages.dev/bots/">the earlier report</a>. "People" or "everyone else" means every other account. A few of those may be automated too; none shows the block's signature.</li>
    <li><b>Year-long like lists.</b> The complete public like list of every public artwork with at least one like uploaded between 5 October 2025 and 5 October 2026 ({num(B["artworks_liked"])} artworks, {num(B["likes"])} likes), read on 6 October 2026, plus the {num(B["artworks"] - B["artworks_liked"])} artworks of the same period with no like. Like lists carry no timestamps, only order, newest first. Sections 1 to 3 use the artworks uploaded 5 April to 6 September 2026, one to six months old at the read, because the block's activity was ramping up before that: uploads from late 2025 carry fewer block likes than later ones, a matter of when they were posted rather than what they are.</li>
    <li><b>Hourly like events.</b> From 5 October to 3 November 2026, every hour, the newest likers of every recent artwork whose like count had risen, so each like is dated to the hour ({num(E["likes"])} likes on {num(E["artworks"])} artworks; {num(E["fresh_block"] + E["fresh_human"])} of them on uploads made in the period). Seven gaps longer than two hours, the longest {E["longest_gap_h"]:g} hours; the hour-of-day chart averages over the reads that happened. Hourly coverage is reliable for about the first two weeks of an artwork's life, so the rate charts stop at 48 hours and 14 days.</li>
    <li><b>Older artworks.</b> Every two days, the newest likers of artworks older than 30 days whose counter had risen, the most active ones first. This gives the block's share of new likes by age, not a rate.</li>
    <li><b>Uploader tiers.</b> Master Pixel Artist: the account carries Divoom's ambassador badge in any listing we read. Featured: the accounts servoom names on its statistics pages (Divoom's Expert list, badge holders, or three or more Recommend picks in the year), without the badge holders. Divoom's Expert list is not stored on its own, so "featured" is the nearest available tier.</li>
    <li><b>Model.</b> Ordinary least squares on log(1 + block likes) with log(1 + human likes), age, tier, curation, type, category and canvas as inputs, {num(O["n"])} artworks. Multipliers are the exponentials of the coefficients.</li>
    <li><b>What was not read.</b> Private, held and deleted uploads; the Chinese app servers; anything requiring an account other than the throwaway read-only ones servoom uses, which never liked, followed, commented or uploaded.</li>
  </ul>
</section>

<footer>servoom · November 2026 · This page is a description of behaviour observed on the public gallery and makes no claim about who operates the accounts beyond what the earlier report argues.</footer>
</div>
"""

(OUT / "liking.html").write_text(body, encoding="utf8")
print("wrote", OUT / "liking.html", len(body), "bytes")
