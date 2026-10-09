"""Collect bot evidence for given UserIds with the fresh bots_check_01 account (read-only)
and the local servoom-raw like records. Writes out/evidence_<uid>.json and out/report_data.json."""
import glob, json, sys, time
from collections import Counter
from pathlib import Path
import pandas as pd, pyarrow.parquet as pq
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RAW = ROOT.parent / "servoom-raw"
sys.path.insert(0, str(ROOT / "python"))
from servoom.client import DivoomClient
from credentials import TEST_ACCOUNTS

BLOCK = (400971852, 400975850)
uids = [int(x) for x in sys.argv[1:]]
a = TEST_ACCOUNTS["bots_check_01"]
c = DivoomClient(email=a["email"], md5_password=a["md5"])
assert c.login()

# local catalog crawl (whole catalog, 2026-10-05/07) and like records
chg = pd.concat([pq.read_table(f).to_pandas() for f in glob.glob(str(RAW / "obs/snapshot/**/changes-*.parquet"), recursive=True)])
chg = chg.sort_values("t").drop_duplicates("gid", keep="last")
likes = pd.read_parquet(HERE.parents[2].parent / "AppData/Local/Temp/claude/C--Users-fab-F-Estudo-Tecnologia-servoom-repo/e51f167b-03c5-4add-8530-99ea7ed8d9a2/scratchpad/likes.parquet") if False else None
lk = pd.concat([pq.read_table(f).to_pandas()[["gid", "liker", "t"]] for f in
                glob.glob(str(RAW / "obs/likes-backfill/*.parquet")) + glob.glob(str(RAW / "obs/pulse/**/*-likes.parquet"), recursive=True)
                + glob.glob(str(RAW / "obs/snapshot/**/likes.parquet"), recursive=True)])
lk = lk.drop_duplicates(["gid", "liker"])
blk = lk[(lk.liker >= BLOCK[0]) & (lk.liker <= BLOCK[1])]
per_block = blk.groupby("liker").size()
# originals: catalog artworks dated before 2019 owned outside the block, keyed by (date)
early = chg[(chg.date < 1546300800)]
early_nonblock = early[(early.uid < BLOCK[0]) | (early.uid > BLOCK[1])]
date_owner = early_nonblock.groupby("date")["uid"].apply(set)

report = {}
for uid in uids:
    info = c.fetch_someone_info(uid) or {}
    arts = c.fetch_someone_arts(uid, limit=500)
    time.sleep(0.5)
    rows = []
    for x in arts:
        d = x.get("Date")
        orig = sorted(date_owner.get(d, set()))[:5]
        rows.append({"GalleryId": x.get("GalleryId"), "FileId": x.get("FileId"), "FileName": x.get("FileName"),
                     "Date": d, "DateISO": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(d)) if d else None,
                     "LikeCnt": x.get("LikeCnt"), "WatchCnt": x.get("WatchCnt"), "CommentCnt": x.get("CommentCnt"),
                     "same_date_nonblock_owners": orig})
    # local like-giving record
    mine = lk[lk.liker == uid].sort_values("t")
    ts = mine["t"].to_numpy()
    liked_owners = chg.set_index("gid")["uid"].reindex(mine["gid"]).dropna()
    gaps = pd.Series(ts[1:] - ts[:-1]) if len(ts) > 1 else pd.Series(dtype=float)
    hours = Counter(pd.to_datetime(ts, unit="s").hour.tolist())
    ev = {
        "profile": {k: info.get(k) for k in ("NickName", "Level", "Score", "LikeCnt", "FansCnt", "FollowCnt",
                                            "CountryISOCode", "RegionId", "HeadId", "UserNewSign", "MedalList")},
        "in_like_block": BLOCK[0] <= uid <= BLOCK[1] and uid % 2 == 0,
        "artworks": {"count": len(rows), "dates_min": min((r["DateISO"] for r in rows if r["Date"]), default=None),
                     "dates_max": max((r["DateISO"] for r in rows if r["Date"]), default=None),
                     "with_pre2019_original_same_second": sum(1 for r in rows if r["same_date_nonblock_owners"]),
                     "even_gallery_ids": sum(1 for r in rows if r["GalleryId"] and r["GalleryId"] % 2 == 0),
                     "total_comments": sum(r["CommentCnt"] or 0 for r in rows), "list": rows},
        "likes_given_observed": {
            "count": int(len(mine)), "distinct_artworks": int(mine.gid.nunique()), "distinct_owners": int(liked_owners.nunique()),
            "first": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(ts.min())) if len(ts) else None,
            "last": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(ts.max())) if len(ts) else None,
            "median_gap_s": float(gaps.median()) if len(gaps) else None,
            "by_utc_hour": {str(h): hours.get(h, 0) for h in range(24)},
            "block_rank_percentile": float((per_block < len(mine)).mean()) if len(mine) else None,
            "block_mean_likes_per_account": float(per_block.mean()),
        },
    }
    report[uid] = ev
    (HERE / "out" / f"evidence_{uid}.json").write_text(json.dumps(ev, indent=1, ensure_ascii=False), encoding="utf-8")
    print(uid, ev["profile"]["NickName"], "arts", len(rows), "pre2019-original-same-second", ev["artworks"]["with_pre2019_original_same_second"],
          "likes_given", len(mine), "owners", int(liked_owners.nunique()), "median_gap", ev["likes_given_observed"]["median_gap_s"])
(HERE / "out" / "report_data.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
