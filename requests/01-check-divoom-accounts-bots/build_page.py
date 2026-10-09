"""Build the shareable evidence page (out/bots-page.html) from out/pairs_final.json,
out/evidence_*.json and out/block_profiles.jsonl. Artwork thumbnails are inlined as
data URIs; original uploaders are shown by UserId only."""
import base64, html, json, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; OUT = HERE / "out"

pairs = json.loads((OUT / "pairs_final.json").read_text(encoding="utf-8"))
ev = {u: json.loads((OUT / f"evidence_{u}.json").read_text(encoding="utf-8")) for u in (400973210, 400975304)}
block = [json.loads(l) for l in (OUT / "block_profiles.jsonl").open(encoding="utf-8")]
countries = len({b.get("CountryISOCode") for b in block if b.get("CountryISOCode")})
zero_follow = sum(1 for b in block if b.get("FollowCnt") == 0)
levels = sorted({b.get("Level") for b in block if b.get("Level") is not None})

def uri(name):
    return "data:image/png;base64," + base64.b64encode((OUT / "pairs" / name).read_bytes()).decode()
def iso(ts):
    return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(ts))
def esc(s):
    return html.escape(str(s))

cards = []
for p in pairs:
    cards.append(f"""
<figure class="pair">
  <div class="pair-imgs">
    <div class="tile"><img src="{uri(p['bot_png'])}" alt="" width="128" height="128"><span class="tag bot">{esc(p['bot'])}</span></div>
    <div class="tile"><img src="{uri(p['orig_png'])}" alt="" width="128" height="128"><span class="tag">original</span></div>
  </div>
  <figcaption>
    <b>{esc(p['bot_title'].strip())}</b>
    <span>uploaded {esc(iso(p['bot_date']))}</span>
    <span>original by user {p['orig_uid']} (artwork #{p['orig_gid']}) at the same second</span>
    <span class="mono">file {p['bot_bytes']} bytes, identical md5 {p['bot_md5'][:10]}…</span>
  </figcaption>
</figure>""")

def acct_row(name, uid, img_label):
    e = ev[uid]; pr = e["profile"]; a = e["artworks"]; l = e["likes_given_observed"]
    copies = sum(1 for p in pairs if p["bot_uid"] == uid)
    return f"""
<tr><th scope="row">{name}</th><td class="mono">{uid}</td><td>{pr['Level']}</td><td>{pr['Score']}</td><td>{pr['LikeCnt']}</td><td>{pr['FansCnt']}</td><td>{pr['FollowCnt']}</td><td>{pr['CountryISOCode']}</td><td>{a['count']}</td><td>{copies}</td><td>{l['count']}</td><td>{l['distinct_owners']}</td></tr>"""

page = f"""<title>Are Drew and julycat bots?</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Silkscreen:wght@400;700&family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;1,400&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Layout: one reading column; evidence as numbered exhibits, each with a verdict chip; a pixel-art gallery of copied works. */
:root {{
  --bg: #f6f4ee; --surface: #fffdf8; --fg: #1d1b16; --muted: #6a6557; --line: #d9d4c6;
  --accent: #d9790a; --accent-ink: #8a4a00; --bad: #b4231e; --bad-bg: #fbe9e6; --ok: #2b7a3f;
  --display: "Silkscreen", "Courier New", monospace;
  --body: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
  --mono: "IBM Plex Mono", Consolas, monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg: #15171c; --surface: #1d2027; --fg: #ecebe4; --muted: #a39f93; --line: #343843;
  --accent: #f0a030; --accent-ink: #f7c87a; --bad: #ff6b60; --bad-bg: #3a1f1d; --ok: #6fcf8a; color-scheme: dark }} }}
:root[data-theme="dark"] {{
  --bg: #15171c; --surface: #1d2027; --fg: #ecebe4; --muted: #a39f93; --line: #343843;
  --accent: #f0a030; --accent-ink: #f7c87a; --bad: #ff6b60; --bad-bg: #3a1f1d; --ok: #6fcf8a; color-scheme: dark }}
body {{ background: var(--bg); color: var(--fg); font-family: var(--body); font-size: 16px; line-height: 1.55; }}
.wrap {{ max-width: 760px; margin: 0 auto; padding-inline: 20px; padding-block: 40px 64px; }}
h1, h2, h3 {{ text-wrap: balance; line-height: 1.2; margin: 0; }}
h1 {{ font-family: var(--display); font-size: clamp(26px, 5vw, 38px); font-weight: 700; letter-spacing: -0.5px; }}
h2 {{ font-family: var(--display); font-size: 17px; font-weight: 700; margin-top: 44px; }}
h3 {{ font-size: 17px; font-weight: 600; margin-top: 20px; }}
p {{ margin: 12px 0; max-width: 66ch; }}
.eyebrow {{ font-family: var(--display); font-size: 11px; letter-spacing: 2px; text-transform: uppercase; color: var(--accent-ink); }}
.lead {{ font-size: 18px; }}
.verdict {{ margin-top: 24px; border-left: 6px solid var(--bad); background: var(--bad-bg); padding: 16px 20px; border-radius: 0 6px 6px 0; }}
.verdict .big {{ font-family: var(--display); font-size: 22px; color: var(--bad); }}
.verdict p {{ margin: 6px 0 0; }}
.muted {{ color: var(--muted); }}
.mono {{ font-family: var(--mono); font-size: 0.92em; }}
table {{ border-collapse: collapse; width: 100%; font-size: 14px; font-variant-numeric: tabular-nums; }}
.tablewrap {{ overflow-x: auto; margin: 16px 0; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); }}
th, td {{ padding: 8px 10px; text-align: right; border-bottom: 1px solid var(--line); white-space: nowrap; }}
th {{ font-weight: 600; }} th[scope=row], td:first-child {{ text-align: left; }}
thead th {{ text-align: right; color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }}
thead th:first-child {{ text-align: left; }}
tbody tr:last-child td, tbody tr:last-child th {{ border-bottom: 0; }}
.exhibit {{ display: grid; grid-template-columns: 1fr; gap: 6px; margin-top: 28px; padding-top: 18px; border-top: 1px solid var(--line); }}
.exhibit header {{ display: flex; flex-wrap: wrap; align-items: baseline; gap: 10px 14px; }}
.chip {{ font-family: var(--display); font-size: 10px; letter-spacing: 1px; text-transform: uppercase; padding: 3px 8px; border-radius: 3px; border: 1px solid currentColor; }}
.chip.strong {{ color: var(--bad); }} .chip.support {{ color: var(--accent-ink); }}
.gallery {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 14px; margin: 18px 0; }}
.pair {{ margin: 0; background: var(--surface); border: 1px solid var(--line); border-radius: 6px; padding: 12px; min-width: 0; }}
.pair-imgs {{ display: flex; gap: 10px; }}
.tile {{ position: relative; flex: 0 0 auto; }}
.tile img {{ display: block; width: 112px; height: 112px; image-rendering: pixelated; border: 1px solid var(--line); background: #000; }}
.tag {{ position: absolute; left: 4px; bottom: 4px; font-family: var(--display); font-size: 9px; letter-spacing: 1px; text-transform: uppercase; padding: 2px 5px; background: rgba(255,255,255,.9); color: #1d1b16; border-radius: 2px; }}
.tag.bot {{ background: var(--bad); color: #fff; }}
figcaption {{ display: grid; gap: 2px; margin-top: 10px; font-size: 13px; color: var(--muted); }}
figcaption b {{ color: var(--fg); font-size: 14px; }}
ul {{ padding-left: 20px; max-width: 66ch; }} li {{ margin: 6px 0; }}
.foot {{ margin-top: 48px; padding-top: 16px; border-top: 1px solid var(--line); font-size: 13px; color: var(--muted); }}
a {{ color: var(--accent-ink); }}
@media (max-width: 480px) {{ .tile img {{ width: 96px; height: 96px; }} .wrap {{ padding-inline: 16px; }} }}
@media (prefers-reduced-motion: no-preference) {{ .pair:hover img {{ transition: transform .15s; transform: scale(1.02); }} }}
</style>

<div class="wrap">
<div class="eyebrow">Divoom pixel-art community · account check · 2026-10-09</div>
<h1 style="margin-top:10px">Are Drew and julycat bots?</h1>
<p class="lead">Two Divoom accounts, <b>Drew</b> and <b>julycat</b>, were checked because their likes and follows looked suspicious. This page lays out what was found and how sure we can be.</p>

<div class="verdict">
  <div class="big">Yes. Both are automated accounts.</div>
  <p>Confidence is as high as this kind of question allows. Every artwork they "posted" is a byte-for-byte copy of another user's 2018 upload, they belong to a batch of 2,000 identical accounts created in one block, and each of them hands out roughly 500 likes every few days to hundreds of strangers while following nobody. No human account looks like this.</p>
</div>

<h2>The two accounts</h2>
<p>Both profiles were located from the screenshots and read directly from Divoom's servers. The numbers below match the screenshots exactly.</p>
<div class="tablewrap"><table>
<thead><tr><th>Name</th><th>User id</th><th>Level</th><th>Score</th><th>Likes received</th><th>Followers</th><th>Following</th><th>Country</th><th>Artworks</th><th>Proven copies</th><th>Likes given, 3 days</th><th>Artists liked</th></tr></thead>
<tbody>{acct_row("julycat", 400973210, "")}{acct_row("Drew", 400975304, "")}</tbody>
</table></div>
<p class="muted">"Likes given" counts the likes we observed from each account between 2026-10-05 and 2026-10-08 while watching the public like lists of recent uploads. The true number is higher, since only part of the catalog was watched.</p>

<h2>The evidence</h2>
<p>Four independent lines of evidence point the same way. Any one of them would be enough to doubt the accounts. Together they leave no room for a human explanation.</p>

<section class="exhibit">
<header><h3>1. Every artwork is a stolen file</h3><span class="chip strong">decisive</span></header>
<p>Drew shows 15 artworks and julycat 11. We found the original of 19 of them (11 of Drew's, 8 of julycat's) in the public gallery. In every case the bot's copy carries the <b>same title</b>, the <b>same upload timestamp to the second</b>, and a file that is <b>identical byte for byte</b> (same size, same checksum) to a 2018 upload by an ordinary user. The remaining artworks are the same kind of 2018 copy whose originals have since been deleted by their owners.</p>
<p>A person cannot upload a file at the exact second someone else did, years earlier. These entries were inserted into the database wholesale, not drawn and posted by anyone.</p>
<div class="gallery">{''.join(cards)}</div>
<p class="muted">Left: the bot account's copy. Right: the original, by the user whose id is shown. Thumbnails are the first frame of each 16×16 artwork. Originals are shown for comparison only and remain their authors' work.</p>
</section>

<section class="exhibit">
<header><h3>2. They are two of 2,000 accounts made in one batch</h3><span class="chip strong">decisive</span></header>
<p>Divoom assigns user ids in sequence. Drew is id 400975304 and julycat is id 400973210. Both fall inside a block of exactly 4,000 consecutive ids (400971852 to 400975850) that is unlike anything else on the platform:</p>
<ul>
<li>Only the <b>even</b> ids in that range exist. The odd ones were never issued. Everywhere else on Divoom, ids are mostly odd (international sign-ups) with some even (China-region sign-ups).</li>
<li>All 2,000 accounts in the block have the same profile shape: a handful of 2018-dated copied artworks, the same stock medal icons, an empty bio, and <b>{zero_follow:,} of 2,000 follow nobody</b>.</li>
<li>Their declared countries are spread evenly over <b>{countries} countries</b>. Drew is in the Central African Republic and julycat in Uzbekistan, both drawn from that random spread.</li>
<li>Across the block the accounts own about <b>17,800 artworks</b>, which are copies of just <b>880 early files</b>, inserted in November and December 2020 with consecutive even artwork ids. Drew's artworks are ids 812710 to 812740 and julycat's are 791358 to 791382, all even, all two apart.</li>
</ul>
<p>Two accounts picked by chance from a crowd of real users do not both land inside a reserved, half-empty id block whose every member looks the same.</p>
</section>

<section class="exhibit">
<header><h3>3. They like on an industrial scale</h3><span class="chip strong">decisive</span></header>
<p>In three days of watching, julycat liked <b>488</b> artworks by <b>283</b> different artists and Drew liked <b>493</b> by <b>270</b>, never the same artwork twice. The block's 2,000 members all do the same: in the same window their per-account counts range from 417 to 574 with an average of 483, a flat, machine-made distribution. The two accounts sit right in the middle of it.</p>
<p>Taken together, this block produces roughly <b>two thirds of all likes on Divoom</b>: about 10,000 of the 16,000 likes the platform records on a typical day. The likes arrive one to three at a time from a uniformly random block account, which is why a real user's new upload collects a trickle of likes from accounts like Drew and julycat within hours of posting. Those likes are not an audience. They are a counter being incremented.</p>
</section>

<section class="exhibit">
<header><h3>4. Nothing human has ever happened on them</h3><span class="chip support">supporting</span></header>
<ul>
<li>Neither account follows anyone, although both have followers.</li>
<li>Not one comment has ever been left on any of their 26 artworks, and the only comments the block has ever written came in two block-wide campaigns (2021 and spring 2026). In the 2021 one the server itself marked the block's comments with its internal <span class="mono">RobertFlag</span> (robot flag) field.</li>
<li>Their stats do not add up the way a real account's do: Drew is level 1 with a score of 514 while julycat is level 10 with a score of 335. Levels in the block range from {levels[0]} to {levels[-1]} with no relation to activity.</li>
<li>The bio is empty, the avatar is a stock pixel image, and the "works" never change.</li>
</ul>
</section>

<h2>How confident, and what remains unknown</h2>
<p><b>That they are bots: certain for all practical purposes.</b> The identical-file evidence alone rules out a person, and the batch and liking patterns confirm it independently. Nothing we could still learn about these accounts would make them human.</p>
<p><b>Who runs them: probably Divoom itself.</b> This is an inference, not a proven fact. The block's ids were reserved in one piece, its artworks were inserted directly into the database with copied timestamps, its comments were once tagged with the server's own robot flag, and the accounts have been left in place for years. Each of these would be hard for an outsider to do and easy for the platform operator. No public statement from Divoom about these accounts has been found.</p>

<h2>What this means for you</h2>
<ul>
<li>Likes and follows from Drew, julycat, or any even-numbered id between 400971852 and 400975850 carry no information about how people received your work.</li>
<li>Because the block supplies about two thirds of all likes, a like count on Divoom is best read with that share removed. The comments and the follows from real accounts are the honest signal.</li>
<li>There is nothing to do about the accounts themselves. Blocking them only hides their likes from your view.</li>
</ul>

<div class="foot">Data read from Divoom's public API on 2026-10-09 with a fresh, read-only account, together with like observations from 2026-10-05 to 2026-10-08. Background measurements of the 2,000-account block come from the <a href="https://servoom.pages.dev/">servoom</a> project's community statistics. Original artworks are shown for comparison only.</div>
</div>
"""
(OUT / "bots-page.html").write_text(page, encoding="utf-8")
print("wrote", OUT / "bots-page.html", len(page) // 1024, "KB; block countries", countries, "zero-follow", zero_follow, "levels", levels[0], levels[-1])
