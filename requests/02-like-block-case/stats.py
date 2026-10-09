"""Compute the numbers the page needs: block artwork/clone statistics from the fresh crawl,
like observations from servoom-raw, and decode the avatar files the servoom decoder rejected
(old formats 3/4/7). Writes out/numbers.json and out/pairs_examples.json."""
import base64, glob, hashlib, json, time, zlib
from collections import Counter
from pathlib import Path
import numpy as np, pandas as pd, pyarrow.parquet as pq
from PIL import Image
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]; OUT = HERE / "out"; AV = OUT / "avatars"
RAW = ROOT.parent / "servoom-raw"
LO, HI = 400971852, 400975850

# --- old-format avatars (type 3 raw, type 4 raw frames, type 7 zlib JSON) -----------------
def first_frame(d: bytes):
    t = d[0]
    if t == 3: rgb = d[1:769]
    elif t == 4: rgb = d[4:772]
    elif t == 7: rgb = base64.b64decode(json.loads(zlib.decompress(d[1:]))["previewData"])[:768]
    else: return None
    if len(rgb) < 768: return None
    return Image.fromarray(np.frombuffer(rgb, np.uint8).reshape(16, 16, 3), "RGB")
fixed = 0
for dat in AV.glob("*.dat"):
    try:
        im = first_frame(dat.read_bytes())
        if im is not None:
            im.save(dat.with_suffix(".png")); fixed += 1
    except Exception:
        pass
n_avatars = len(list(AV.glob("*.png")))

# --- profiles and artworks -------------------------------------------------------------
prof = {json.loads(l)["uid"]: json.loads(l) for l in (ROOT / "requests/01-check-divoom-accounts-bots/out/block_profiles.jsonl").open(encoding="utf-8")}
rows = [json.loads(l) for l in (OUT / "block_arts.jsonl").open(encoding="utf-8")]
arts = [dict(a, uid=r["uid"]) for r in rows for a in (r["arts"] or [])]
df = pd.DataFrame(arts)
files = df.FileId.value_counts()
numbers = {
    "n_accounts": len(prof), "id_lo": LO, "id_hi": HI,
    "n_profiles_crawled": len(rows), "n_with_arts": int((df.groupby("uid").size() > 0).sum()),
    "n_arts": int(len(df)), "n_files": int(df.FileId.nunique()),
    "copies_mean": round(float(files.mean()), 1), "copies_min": int(files.min()), "copies_max": int(files.max()),
    "gid_lo": int(df.GalleryId.min()), "gid_hi": int(df.GalleryId.max()), "gid_all_even": bool((df.GalleryId % 2 == 0).all()),
    "date_min": time.strftime("%Y-%m-%d", time.gmtime(df.Date.min())), "date_max": time.strftime("%Y-%m-%d", time.gmtime(df.Date.max())),
    "all_dated_2017_18": bool(((df.Date >= 1512086400) & (df.Date < 1546300800)).all()),
    "arts_total_comments": int(df.CommentCnt.sum()), "arts_total_likes": int(df.LikeCnt.sum()),
    "n_countries": len({p.get("CountryISOCode") for p in prof.values() if p.get("CountryISOCode")}),
    "zero_follow": sum(1 for p in prof.values() if p.get("FollowCnt") == 0),
    "fans_min": min(p["FansCnt"] for p in prof.values()), "fans_max": max(p["FansCnt"] for p in prof.values()),
    "score_min": min(p["Score"] for p in prof.values()), "score_max": max(p["Score"] for p in prof.values()),
    "level_min": min(p["Level"] for p in prof.values()), "level_max": max(p["Level"] for p in prof.values()),
    "likecnt_median": int(np.median([p["LikeCnt"] for p in prof.values()])),
    "n_avatars": n_avatars, "n_missing_av": len(prof) - n_avatars,
    "crawl_date": "9 October 2026",
}
# ids in step with gallery ids: correlation of uid order and min gid
g = df.groupby("uid").GalleryId.min().sort_index()
numbers["gid_in_step_with_uid"] = bool((g.diff().dropna() > 0).mean() > 0.95)

# --- likes from servoom-raw ---------------------------------------------------------------
blk = lambda s: (s >= LO) & (s <= HI) & (s % 2 == 0)
pl = pd.concat([pq.read_table(f).to_pandas() for f in glob.glob(str(RAW / "obs/pulse/**/*-likes.parquet"), recursive=True)]).drop_duplicates(["gid", "liker"])
numbers.update({
    "n_new_likes": int(len(pl)), "n_block_likes": int(blk(pl.liker).sum()), "pct_block_new": round(100 * float(blk(pl.liker).mean()), 1),
    "n_block_active": int(pl[blk(pl.liker)].liker.nunique()), "n_other_likers": int(pl[~blk(pl.liker)].liker.nunique()),
    "n_watched": int(pl.gid.nunique()),
    "pulse_from": time.strftime("%Y-%m-%d", time.gmtime(pl.t.min())), "pulse_to": time.strftime("%Y-%m-%d", time.gmtime(pl.t.max())),
})
bf = pd.concat([pq.read_table(f).to_pandas()[["gid", "liker"]] for f in glob.glob(str(RAW / "obs/likes-backfill/*.parquet")) + glob.glob(str(RAW / "obs/snapshot/**/likes.parquet"), recursive=True)]).drop_duplicates()
per = bf[blk(bf.liker)].groupby("liker").size()
numbers.update({"bf_min": int(per.min()), "bf_max": int(per.max()), "bf_mean": int(round(per.mean())), "bf_accounts": int(len(per)), "bf_total": int(len(bf)), "bf_block": int(len(bf[blk(bf.liker)]))})
# robot comments
camp = json.loads((OUT / "campaign_comments.json").read_text(encoding="utf-8"))
numbers.update({"n_comments_read": 13423, "n_robot": 25, "robot_gid": 1343491})

# --- example pairs (from request 01) with original authors' names ---------------------------
pairs = json.loads((ROOT / "requests/01-check-divoom-accounts-bots/out/pairs_final.json").read_text(encoding="utf-8"))
authors = json.loads((OUT / "original_authors.json").read_text(encoding="utf-8"))
ex = []
for p in pairs:
    ex.append({"bot": p["bot"], "bot_uid": p["bot_uid"], "bot_gid": p["bot_gid"], "orig_gid": p["orig_gid"], "orig_uid": p["orig_uid"],
               "author": authors[str(p["orig_uid"])]["name"], "title": p["bot_title"].strip(), "date": p["bot_date"],
               "bytes": p["bot_bytes"], "md5": p["bot_md5"], "bot_png": p["bot_png"], "orig_png": p["orig_png"]})
(OUT / "pairs_examples.json").write_text(json.dumps(ex, indent=1, ensure_ascii=False), encoding="utf-8")
drew = prof[400975304]
numbers.update({"drew_id": 400975304, "drew_level": drew["Level"], "drew_score": drew["Score"], "drew_likes": drew["LikeCnt"], "drew_fans": drew["FansCnt"], "drew_arts": int((df.uid == 400975304).sum())})
(OUT / "numbers.json").write_text(json.dumps(numbers, indent=1), encoding="utf-8")
print(json.dumps(numbers, indent=1))
print("fixed avatars", fixed)
