"""Build the shareable package from what collect.py saved.

Run from python/:  python ../requests/04-thepixelxb/build.py [--limit N] [--zip]
Idempotent: decoded files that already exist are not rewritten.
"""
import argparse
import csv
import datetime as dt
import json
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "python"))

from servoom.layer_file_decoder import LayerFileDecoder  # noqa: E402
from servoom.pixel_bean_decoder import PixelBeanDecoder  # noqa: E402

PKG = HERE / "package"
ARTS = PKG / "artworks"
ARTIST = "ThePixelXḃ_"
USER_ID = 400791502


def ts(epoch):
    return dt.datetime.fromtimestamp(epoch, dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def flatten_comments(comments, gid, depth=0, parent=""):
    for cm in comments:
        yield {"gallery_id": gid, "comment_id": cm.get("CommentId"), "parent_comment_id": parent,
               "depth": depth, "time_utc": cm.get("Time"), "user_id": cm.get("UserId"),
               "nickname": cm.get("NickName"), "level": cm.get("Level"),
               "country": cm.get("CountryISOCode"), "likes": cm.get("LikeCnt"),
               "reply_to": cm.get("AckUserNickName") or "", "text": cm.get("Content")}
        yield from flatten_comments(cm.get("CommentChildList") or [], gid, depth + 1, cm.get("CommentId"))


def comments_txt(comments, depth=0):
    out = []
    for cm in comments:
        pad = "    " * depth
        to = f" -> {cm['AckUserNickName']}" if cm.get("AckUserNickName") else ""
        out.append(f"{pad}[{cm.get('Time')}] {cm.get('NickName')} (Lv{cm.get('Level')}, "
                   f"{cm.get('CountryISOCode')}){to}: {cm.get('Content')}")
        out.extend(comments_txt(cm.get("CommentChildList") or [], depth + 1))
    return out


def decode_folder(d, meta, errors):
    gid = meta["gallery"]["GalleryId"]
    row = {}
    for what in meta.get("missing", []):
        errors.append((d.name, f"{what} file no longer on the Divoom server (404)"))
    webp, gif = d / f"{gid}.webp", d / f"{gid}.gif"
    if "artwork" not in meta["files"]:
        pass
    elif not (webp.exists() and gif.exists()):
        dat = d / meta["files"]["artwork"]
        first = dat.read_bytes()[:1]
        bean = None if first in (b"", b"", b"") else PixelBeanDecoder.decode_file(str(dat))
        if bean is None:
            kind = {b"": "Planet lamp file (28 LEDs, not an image) / Planet 灯文件（28 颗 LED，非图像）",
                    b"": "Planet lamp animation (28 LEDs, not an image) / Planet 灯动画（28 颗 LED，非图像）",
                    b"": "LED text artwork, not decoded / LED 文字作品，未解码"}.get(first, "artwork decode failed / 作品解码失败")
            errors.append((d.name, kind))
        else:
            bean.save_to_webp(str(webp))
            bean.save_to_gif(str(gif))
            row.update(width=bean.width, height=bean.height, frames=bean.total_frames, speed_ms=bean.speed)
    else:
        from PIL import Image
        with Image.open(webp) as im:
            row.update(width=im.width, height=im.height, frames=getattr(im, "n_frames", 1))
    if "layer" in meta["files"]:
        psd = d / f"{gid}_layer.psd"
        if not psd.exists():
            try:
                layer = LayerFileDecoder.decode_file(str(d / meta["files"]["layer"]))
                layer.save_to_psd(str(psd))
                row.update(layer_frames=layer.num_frames, layers=layer.total_layers)
            except Exception as exc:
                errors.append((d.name, f"layer decode failed: {exc}"))
    likes, comments = meta["likes"], meta["comments"]
    with (d / "likes.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["user_id", "nickname", "level", "country", "fans", "score"])
        for u in likes:
            w.writerow([u.get("UserId"), u.get("NickName"), u.get("Level"), u.get("CountryISOCode"),
                        u.get("FansCnt"), u.get("Score")])
    lines = comments_txt(comments)
    (d / "comments.txt").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return row


HTML_HEAD = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>__ARTIST__ - Divoom archive</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--bg:#111;--fg:#eee;--mut:#999;--card:#1b1b1b;--acc:#7cc}
body{margin:0;font:14px/1.4 system-ui,-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--fg)}
header{padding:16px 20px;border-bottom:1px solid #333;position:sticky;top:0;background:var(--bg);z-index:2}
h1{margin:0 0 6px;font-size:20px} .sub{color:var(--mut)}
.bar{display:flex;gap:10px;flex-wrap:wrap;margin-top:10px;align-items:center}
input,select{background:#222;color:var(--fg);border:1px solid #444;border-radius:6px;padding:6px 8px;font:inherit}
#grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px;padding:16px 20px}
.card{background:var(--card);border-radius:8px;padding:8px;cursor:pointer}
.card img{width:100%;aspect-ratio:1;image-rendering:pixelated;background:#000;border-radius:4px;display:block}
.t{margin-top:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis} .m{color:var(--mut);font-size:12px}
#dlg{max-width:900px;width:95vw;background:var(--card);color:var(--fg);border:1px solid #444;border-radius:10px;padding:16px}
#dlg::backdrop{background:#0009} #dlg img{width:min(40vw,320px);image-rendering:pixelated;background:#000;float:left;margin:0 16px 8px 0}
#dlg h2{margin:0 0 6px;font-size:18px} #dlg a{color:var(--acc)}
pre{white-space:pre-wrap;clear:both;background:#000;padding:10px;border-radius:6px;max-height:40vh;overflow:auto}
.x{float:right;cursor:pointer;font-size:20px}
</style></head><body>
<header><h1>__ARTIST__ <span class="sub">&middot; Divoom archive / 作品存档 &middot; UserId __UID__</span></h1>
<div class="sub">__N__ artworks / 件作品 &middot; __LIKES__ likes / 赞 &middot; __VIEWS__ views / 浏览 &middot; __COMMENTS__ comments / 评论 &middot; exported / 导出于 __DATE__</div>
<div class="bar">
<input id="q" placeholder="Search title / 搜索标题" size="30">
<select id="sz"><option value="">All sizes / 全部尺寸</option></select>
<select id="so"><option value="date">Newest first / 最新</option><option value="likes">Most liked / 最多赞</option><option value="views">Most viewed / 最多浏览</option><option value="comments">Most commented / 最多评论</option><option value="old">Oldest first / 最早</option></select>
<span id="cnt" class="sub"></span></div></header>
<div id="grid"></div>
<dialog id="dlg"></dialog>
<script>
const A=__DATA__;
"""

HTML_TAIL = """
const g=document.getElementById('grid'),q=document.getElementById('q'),sz=document.getElementById('sz'),so=document.getElementById('so'),cnt=document.getElementById('cnt'),dlg=document.getElementById('dlg');
[...new Set(A.map(a=>a.size))].sort((x,y)=>parseInt(x)-parseInt(y)).forEach(s=>{const o=document.createElement('option');o.value=o.textContent=s;sz.appendChild(o)});
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function render(){const t=q.value.toLowerCase();let L=A.filter(a=>(!t||a.title.toLowerCase().includes(t))&&(!sz.value||a.size===sz.value));
const k=so.value;L.sort((x,y)=>k==='old'?x.date-y.date:k==='date'?y.date-x.date:y[k]-x[k]);cnt.textContent=L.length+' shown / 显示';
g.innerHTML=L.map(a=>`<div class="card" data-i="${A.indexOf(a)}"><img loading="lazy" src="${esc(a.img)}" alt=""><div class="t" title="${esc(a.title)}">${esc(a.title)}</div><div class="m">${a.day} &middot; ${a.size} &middot; ${a.frames}f &middot; &hearts;${a.likes} &middot; &#128065;${a.views} &middot; &#128172;${a.comments}</div></div>`).join('')}
g.onclick=e=>{const c=e.target.closest('.card');if(!c)return;const a=A[+c.dataset.i];
dlg.innerHTML=`<span class="x" onclick="dlg.close()">&#10005;</span><h2>${esc(a.title)}</h2><img src="${esc(a.img)}" alt="">
<div>GalleryId ${a.id} &middot; ${a.day} &middot; ${a.size} &middot; ${a.frames} frames/帧${a.layers?' &middot; '+a.layers+' layers/图层':''}${a.music?' &middot; &#127925; sound/音频':''}</div>
<div>&hearts; ${a.likes} likes/赞 &middot; &#128065; ${a.views} views/浏览 &middot; &#128172; ${a.comments} comments/评论${a.tags.length?' &middot; #'+a.tags.map(esc).join(' #'):''}</div>
<div>Files/文件: <a href="${esc(a.dir)}/" target="_blank">open folder / 打开文件夹</a> &middot; <a href="${esc(a.dir)}/${a.id}.gif" target="_blank">GIF</a> &middot; <a href="${esc(a.dir)}/${a.id}.webp" target="_blank">WebP</a>${a.layers?` &middot; <a href="${esc(a.dir)}/${a.id}_layer.psd">PSD</a>`:''} &middot; <a href="${esc(a.dir)}/${a.id}.dat">.dat</a></div>
<pre>${esc(a.ctext||'(no comments / 暂无评论)')}</pre>`;dlg.showModal()};
q.oninput=sz.onchange=so.onchange=render;render();
</script></body></html>
"""

README = """# __ARTIST__ - Divoom archive / Divoom 作品存档

Exported __DATE__ from the Divoom cloud for UserId __UID__ (__ARTIST__).
导出日期 __DATE__，来自 Divoom 云端，用户 ID __UID__（__ARTIST__）。

**Contents / 内容:** __N__ artworks / 件作品, __NLAYER__ with layer files / 含图层文件,
__NMUSIC__ with sound / 含音频, __LIKES__ likes / 赞, __COMMENTS__ comments / 评论.

## How to browse / 如何浏览

* Open **index.html** in any browser (double-click). Search, filter by size, sort by date / likes / views,
  click a card for details, comments and file links.
* 用浏览器打开 **index.html**（双击即可）。可搜索标题、按尺寸筛选、按日期/赞/浏览排序；点击作品查看详情、评论和文件链接。

## Folder layout / 目录结构

```
index.html              offline gallery / 离线画廊
README.md               this file / 本文件
artworks.csv            one row per artwork / 每件作品一行（Excel 可直接打开）
likes.csv               every like: who liked which artwork / 所有点赞记录
comments.csv            every comment, flat, with reply parent / 所有评论（含回复关系）
profile.json, medals.json   profile and medals as returned by the server / 服务器返回的个人资料与勋章
artworks/
  YYYY-MM-DD_<GalleryId>_<title>/      one folder per artwork, dated by upload / 每件作品一个文件夹
    <id>.dat            original artwork file as stored by Divoom / Divoom 原始作品文件
    <id>_layer.dat      original layer (editor) file, when the artwork has one / 原始图层文件（编辑器文件）
    <id>.webp           lossless animated WebP, pixel-exact / 无损动态 WebP，像素精确
    <id>.gif            animated GIF (opens anywhere) / 动态 GIF（通用）
    <id>_layer.psd      layered PSD from the layer file; groups = frames, layers = editor layers
                        / 图层 PSD；组 = 帧，图层 = 编辑器图层
    <id>_music.aac/m4a  attached sound clip, if any / 附带音频（如有）
    metadata.json       full server records: artwork, likers, threaded comments / 完整服务器数据
    likes.csv           who liked this artwork / 本作品点赞用户
    comments.txt        readable comment thread / 可读评论
```

## Notes / 说明

* `.dat` and `_layer.dat` are Divoom's own formats. The open-source decoders are at
  https://github.com/fabkury/servoom (Python, C, and a browser tool at https://servoom.pages.dev/download/).
* `.dat` 与 `_layer.dat` 为 Divoom 私有格式，开源解码器见 https://github.com/fabkury/servoom
  （Python、C，以及网页版工具 https://servoom.pages.dev/download/）。
* Like lists carry no timestamp (the server does not return one); counts were read at export time
  and may differ slightly from the app.
* 点赞列表没有时间戳（服务器不提供）；统计数字为导出时的数值，可能与 App 略有出入。
* Comment times are as the server reports them (UTC). 评论时间以服务器返回为准（UTC）。
* For older artworks the like list is shorter than the like counter: the counter still includes
  likes from accounts that no longer exist, while the list only returns current accounts. The
  server also stops listing likes after 3,000 entries (three artworks are affected).
* 较早作品的点赞列表少于点赞数：计数器仍包含已注销账号的赞，列表只返回现存账号。
  服务器最多列出 3,000 条点赞（涉及三件作品）。
* Planet-lamp artworks (28 LEDs) and LED-text artworks are kept as raw `.dat` only: they are
  not pixel images.
* Planet 灯作品（28 颗 LED）和 LED 文字作品只保留原始 `.dat`，它们不是像素图像。
* Layer files from 2023–2024 use an older container (first byte 0x1D). servoom decodes it
  since 2026-11-04, so those artworks have a PSD too. The app that flattened them between
  June 2023 and December 2024 applied the Hue/Saturation/Lightness sliders slightly
  differently from today's app, so a PSD re-exported from the editor can differ by a few
  colour steps on layers that use those sliders.
* 2023–2024 年的图层文件使用旧版格式（首字节 0x1D），servoom 自 2026-11-04 起可以解码，
  这些作品也有 PSD。2023 年 6 月至 2024 年 12 月期间 App 对色相/饱和度/亮度滑块的处理
  与现版略有不同，使用了这些滑块的图层在编辑器中重新导出时颜色可能相差几个色阶。
* The Divoom server no longer has the layer file of __NMISSING__ artworks uploaded between 2021 and
  2023 (it answers "not found"); those folders hold the artwork file but no layer file or PSD.
  The list is at the end of this file.
* 2021–2023 期间上传的 __NMISSING__ 件作品，其图层文件已不在 Divoom 服务器上（返回"未找到"），
  这些文件夹只有作品文件，没有图层文件和 PSD。清单见本文末尾。
__ERRORS__"""


def fill(template, **kw):
    for k, v in kw.items():
        template = template.replace(f"__{k.upper()}__", str(v))
    return template


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--zip", action="store_true")
    args = ap.parse_args()

    folders = sorted((d for d in ARTS.iterdir() if (d / "metadata.json").exists()), reverse=True)
    errors, rows, all_likes, all_comments, cards = [], [], [], [], []
    for n, d in enumerate(folders):
        if args.limit and n >= args.limit:
            break
        meta = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
        if not meta.get("complete"):
            continue
        a = meta["gallery"]
        gid = a["GalleryId"]
        try:
            dec = decode_folder(d, meta, errors)
        except Exception as exc:
            errors.append((d.name, repr(exc)))
            dec = {}
        tags = [t.get("TagName", t) if isinstance(t, dict) else t for t in (a.get("FileTagArray") or [])]
        size = f"{dec.get('width', '?')}x{dec.get('height', '?')}"
        rows.append({"gallery_id": gid, "title": a.get("FileName"), "uploaded_utc": ts(a["Date"]), "size": size,
                     "frames": dec.get("frames"), "frame_ms": dec.get("speed_ms"), "layers": dec.get("layers"),
                     "likes": a.get("LikeCnt"), "views": a.get("WatchCnt"), "comments": a.get("CommentCnt"),
                     "shares": a.get("ShareCnt"), "has_layer_file": "layer" in meta["files"],
                     "has_sound": "music" in meta["files"], "copyright_flag": a.get("CopyrightFlag"),
                     "private": a.get("PrivateFlag"), "classify": a.get("Classify"), "file_type": a.get("FileType"),
                     "original_gallery_id": a.get("OriginalGalleryId") or "", "tags": " ".join(map(str, tags)),
                     "folder": d.name})
        for u in meta["likes"]:
            all_likes.append({"gallery_id": gid, "artwork": a.get("FileName"), "user_id": u.get("UserId"),
                              "nickname": u.get("NickName"), "level": u.get("Level"),
                              "country": u.get("CountryISOCode")})
        all_comments.extend(flatten_comments(meta["comments"], gid))
        cards.append({"id": gid, "title": a.get("FileName") or "", "date": a["Date"], "day": ts(a["Date"])[:10],
                      "size": size, "frames": dec.get("frames", 0), "layers": dec.get("layers", 0),
                      "likes": a.get("LikeCnt", 0), "views": a.get("WatchCnt", 0),
                      "comments": a.get("CommentCnt", 0), "music": "music" in meta["files"],
                      "tags": [str(t) for t in tags], "dir": f"artworks/{d.name}",
                      "img": f"artworks/{d.name}/{gid}.webp",
                      "ctext": "\n".join(comments_txt(meta["comments"]))})
        if n % 50 == 0:
            print(f"{n}/{len(folders)} {d.name}", flush=True)

    def write_csv(path, items):
        if not items:
            return
        with path.open("w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(items[0]))
            w.writeheader()
            w.writerows(items)

    write_csv(PKG / "artworks.csv", rows)
    write_csv(PKG / "likes.csv", all_likes)
    write_csv(PKG / "comments.csv", all_comments)

    date = dt.date.today().isoformat()
    tot = dict(artist=ARTIST, uid=USER_ID, n=len(rows), nlayer=sum(r["has_layer_file"] for r in rows),
               nmusic=sum(r["has_sound"] for r in rows), likes=sum(r["likes"] or 0 for r in rows),
               views=sum(r["views"] or 0 for r in rows), comments=sum(r["comments"] or 0 for r in rows), date=date)
    data = json.dumps(cards, ensure_ascii=False).replace("</", "<\\/")
    (PKG / "index.html").write_text(fill(HTML_HEAD, data=data, **tot) + HTML_TAIL, encoding="utf-8")
    gone = [(n, e) for n, e in errors if "no longer on the Divoom server" in e]
    other = [(n, e) for n, e in errors if (n, e) not in gone]
    err = ""
    if other:
        groups = {}
        for n, e in other:
            groups.setdefault(e, []).append(n)
        err += "\n## Files not converted to images / 未转换为图像的文件\n"
        for e, names in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            err += f"\n### {e} ({len(names)})\n\n" + "\n".join(f"* {n}" for n in sorted(names)) + "\n"
    if gone:
        err += ("\n## Files missing on the server / 服务器上缺失的文件\n\n"
                + "\n".join(f"* {n}: {e.split(' file')[0]}" for n, e in sorted(gone)) + "\n")
    tot["nmissing"] = len({n for n, _ in gone})
    (PKG / "README.md").write_text(fill(README, errors=err, **tot), encoding="utf-8")
    print(f"built {len(rows)} artworks, {len(all_likes)} likes, {len(all_comments)} comments, {len(errors)} errors")
    for e in errors:
        print("  ERR", e)
    if args.zip:
        zpath = HERE / f"ThePixelXb_divoom_archive_{date}.zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for p in sorted(PKG.rglob("*")):
                if p.is_file():
                    z.write(p, f"ThePixelXb_divoom_archive/{p.relative_to(PKG).as_posix()}")
        print("zip:", zpath, f"{zpath.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
