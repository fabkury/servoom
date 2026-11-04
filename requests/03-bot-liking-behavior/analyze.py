"""How the 2,000 block accounts choose what to like, from stored observations only.

Inputs (never committed here):
* servoom-raw ``obs/likes-backfill/*.parquet``: complete like lists (newest first) of
  every public artwork with at least one like uploaded 5 Oct 2025 .. 5 Oct 2026, read on
  6 Oct 2026. Columns gid, pos, liker, t, auto.
* servoom-raw ``obs/pulse/**/*-likes.parquet``: every hour, the newest ``dl`` likers of
  each recent artwork whose like count rose by ``dl`` since its previous read at
  ``t_prev``; so each row is one like that happened in (t_prev, t]. 5 Oct .. 3 Nov 2026.
* servoom-raw ``obs/snapshot/**/likes.parquet``: the same for artworks older than 30
  days, every two days (the most-liked ones, capped per run).
* servoom-raw ``obs/pulse/**/*-changes.parquet``: counters of recent artworks at every
  pulse (gid, uid, date, cls, size, like, watch, cmt, new, rec, t).
* servoom-raw branch ``state-snap``: ``catalog.parquet`` (every artwork seen, with
  uploader and flags), ``users.parquet`` (uploaders with the ambassador badge flag),
  ``artist_daily.parquet`` (servoom's featured-artist set).

Outputs: ``out/numbers.json`` (every figure quoted in the page) and ``out/charts.json``
(series for the charts). Run from this directory:  python analyze.py
"""

from __future__ import annotations

import glob
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
RAW = Path(os.environ.get("SERVOOM_RAW", HERE / "../../../servoom-raw")).resolve() / "obs"
STATE = Path(os.environ.get("SERVOOM_STATE", HERE / "out/state")).resolve()

LO, HI = 400971852, 400975850          # the block: even ids in this range
DAY = 86400
BF_READ = 1791302356                   # backfill start (6 Oct 2026 16:00 UTC)
T0 = int(pd.Timestamp("2026-10-05", tz="UTC").timestamp())
T1 = int(pd.Timestamp("2026-11-04", tz="UTC").timestamp())
SIZE_PX = {1: 16, 2: 32, 4: 64, 8: "lamp", 16: 128, 32: 256, 64: "256c"}
CLS_NAME = {0: "NEW", 1: "Default", 2: "LED text", 3: "Character", 4: "Emoji", 5: "Daily", 6: "Nature",
            7: "Icon", 8: "Pattern", 9: "Creative", 12: "Photo", 15: "Gadget", 16: "Business", 17: "Season",
            18: "Recommend", 19: "Planet", 29: "Pixel Coloring", 30: "Pixel Match", 40: "AI"}
HB_EDGES, HB_LABELS = [-1, 0, 2, 5, 10, 20, 50, 100, 10 ** 6], ["0", "1-2", "3-5", "6-10", "11-20", "21-50", "51-100", "100+"]

N: dict = {}       # numbers for the page
C: dict = {}       # chart series


def is_block(u) -> np.ndarray:
    u = np.asarray(u, dtype="int64")
    return (u >= LO) & (u <= HI) & (u % 2 == 0)


def r(x, d=3):
    try:
        return None if x is None or np.isnan(x) else round(float(x), d)
    except TypeError:
        return x


def load_state():
    for b in ("state-snap", "state-backfill"):
        if not (STATE / b).exists():
            (STATE / b).mkdir(parents=True)
            os.system(f'git -C "{RAW.parent}" archive origin/{b} | tar -x -C "{STATE / b}"')


# --------------------------------------------------------------------------- load
load_state()
cat = pd.read_parquet(STATE / "state-snap/catalog.parquet",
                      columns=["gid", "uid", "date", "cls", "size", "like", "watch", "cmt", "rec", "new", "gone", "ftype", "copy", "t"])
users = pd.read_parquet(STATE / "state-snap/users.parquet", columns=["uid", "level", "amb", "cc"])
featured = set(pd.read_parquet(STATE / "state-snap/artist_daily.parquet", columns=["uid"]).uid)
master = set(users[users.amb == 1].uid)
lvl = users.set_index("uid").level


def tier_of(uid) -> np.ndarray:
    uid = pd.Series(np.asarray(uid))
    return np.where(uid.isin(master), "master", np.where(uid.isin(featured), "featured", "regular"))


N["tiers_def"] = {"masters_known": len(master), "featured_no_badge": len(featured - master)}
print("catalog", len(cat), "masters", len(master), "featured(no badge)", len(featured - master))

bf = pd.concat([pd.read_parquet(f) for f in glob.glob(str(RAW / "likes-backfill/*.parquet"))], ignore_index=True)
bf = bf.sort_values("t").drop_duplicates(["gid", "liker"], keep="last")
bf["blk"] = is_block(bf.liker)
assert (bf.blk == bf.auto.astype(bool)).all()

per = bf.groupby("gid").agg(n=("liker", "size"), b=("blk", "sum"), t_read=("t", "max")).reset_index()
per["h"] = per.n - per.b
arts = cat[cat.gid.isin(per.gid)].merge(per, on="gid")
rng = cat[(cat.date >= arts.date.min()) & (cat.date <= arts.date.max()) & (cat.gone == 0)].copy()
rng = rng.merge(per[["gid", "n", "b", "h"]], on="gid", how="left").fillna({"n": 0, "b": 0, "h": 0})
rng["age_d"] = (BF_READ - rng.date) / DAY
rng["tier"] = tier_of(rng.uid)
rng["level"] = rng.uid.map(lvl)
rng["px"] = rng["size"].map(SIZE_PX)
rng["photo"] = rng.cls == 12
print("year range: artworks", len(rng), "with likes", int((rng.n > 0).sum()), "likes", int(rng.n.sum()), "block likes", int(rng.b.sum()))

N["bf"] = {
    "upload_from": "2025-10-05", "upload_to": "2026-10-05", "read_day": "2026-10-06",
    "artworks": int(len(rng)), "artworks_liked": int((rng.n > 0).sum()),
    "likes": int(rng.n.sum()), "block_likes": int(rng.b.sum()), "human_likes": int(rng.h.sum()),
    "block_share": r(rng.b.sum() / rng.n.sum()),
    "reach_any_like": r((rng.n > 0).mean()), "reach_block": r((rng.b > 0).mean()), "reach_human": r((rng.h > 0).mean()),
    "only_block": r(((rng.b > 0) & (rng.h == 0)).mean()),
    "only_human": r(((rng.h > 0) & (rng.b == 0)).mean()),
    "block_accounts_seen": int(bf[bf.blk].liker.nunique()), "human_accounts_seen": int(bf[~bf.blk].liker.nunique()),
    "photo_share": r(rng.photo.mean()),
}

# --------------------------------------------------------------------------- A. coverage by age (cross-section)
bins = [0, 1, 3, 7, 14, 30, 60, 90, 180, 270, 366]
labels = ["<1 d", "1-3 d", "3-7 d", "1-2 w", "2-4 w", "1-2 m", "2-3 m", "3-6 m", "6-9 m", "9-12 m"]
rng["ab"] = pd.cut(rng.age_d, bins, labels=labels, right=False)
C["reach_by_age"] = [{"age": str(k), "n": int(len(d)), "block": r((d.b > 0).mean()), "human": r((d.h > 0).mean()),
                      "any": r((d.n > 0).mean()), "mean_block": r(d.b.mean(), 2), "mean_human": r(d.h.mean(), 2),
                      "median_block": r(d.b.median(), 1), "block_share": r(d.b.sum() / max(d.n.sum(), 1))}
                    for k, d in rng.groupby("ab", observed=True)]
old = rng[(rng.age_d >= 30) & (rng.age_d < 180)].copy()        # mature artworks of the block's steady period (Apr-Sep 2026 uploads)
dist = old.b.clip(upper=15).value_counts(normalize=True).sort_index()
C["block_per_art_dist"] = [{"k": int(k) if k < 15 else "15+", "share": r(v)} for k, v in dist.items()]
disth = old.h.clip(upper=15).value_counts(normalize=True).sort_index()
C["human_per_art_dist"] = [{"k": int(k) if k < 15 else "15+", "share": r(v)} for k, v in disth.items()]
N["old"] = {"n": int(len(old)), "mean_block": r(old.b.mean(), 2), "median_block": r(old.b.median(), 1),
            "p90_block": r(old.b.quantile(.9), 1), "max_block": int(old.b.max()), "var_over_mean": r(old.b.var() / old.b.mean(), 1),
            "mean_human": r(old.h.mean(), 2), "median_human": r(old.h.median(), 1), "p90_human": r(old.h.quantile(.9), 1),
            "var_over_mean_human": r(old.h.var() / old.h.mean(), 1), "max_human": int(old.h.max()),
            "reach_block": r((old.b > 0).mean()), "reach_human": r((old.h > 0).mean()), "block_share": r(old.b.sum() / old.n.sum()),
            "share_0": r((old.b == 0).mean()), "share_ge5": r((old.b >= 5).mean()), "share_ge10": r((old.b >= 10).mean()),
            "share_ge30": r((old.b >= 30).mean()),
            "poisson_share_0": r(np.exp(-old.b.mean())), "poisson_share_ge10": r(1 - __import__("scipy.stats").stats.poisson.cdf(9, old.b.mean()))}
rng["ad"] = rng.age_d.astype(int)
acc = rng[rng.ad <= 365].groupby("ad").agg(n=("gid", "size"), b=("b", "mean"), h=("h", "mean")).reset_index()
C["accumulation"] = [{"d": int(x.ad), "n": int(x.n), "block": r(x.b, 2), "human": r(x.h, 2)} for x in acc.itertuples()]

# --------------------------------------------------------------------------- B. preference (mature artworks, 1-6 months)
bf2 = bf.merge(per[["gid", "n"]], on="gid")
big = bf2[bf2.n >= 10].copy()
big["q"] = np.minimum(((big.pos - 1) * 10 // big.n).astype(int), 9)
C["list_position"] = [{"decile": int(k), "block_share": r(v)} for k, v in big.groupby("q").blk.mean().items()]
N["first_likes"] = {"block_share_all": r(bf.blk.mean()), "first_like_block": r(bf2[bf2.pos == bf2.n].blk.mean()),
                    "newest_like_block": r(bf2[bf2.pos == 1].blk.mean()),
                    "oldest3_block": r(bf2[bf2.pos > bf2.n - 3].blk.mean()), "newest3_block": r(bf2[bf2.pos <= 3].blk.mean())}


def by(df, col, mapping=None, min_n=200):
    rows = []
    for k, d in df.groupby(col, observed=True):
        if len(d) < min_n:
            continue
        rows.append({"key": mapping.get(k, str(k)) if mapping else str(k), "n": int(len(d)),
                     "mean_block": r(d.b.mean(), 2), "median_block": r(d.b.median(), 1),
                     "mean_human": r(d.h.mean(), 2), "median_human": r(d.h.median(), 1),
                     "reach_block": r((d.b > 0).mean()), "block_share": r(d.b.sum() / max(d.n.sum(), 1)),
                     "ratio": r(d.b.sum() / max(d.h.sum(), 1), 2), "mean_views": r(d.watch.mean(), 0)})
    return rows


old["cur"] = np.where(old.rec == 1, "Recommend pick", np.where(old.new == 1, "NEW pick", "not curated"))
old["lvl_band"] = pd.cut(old.level.fillna(0), [-1, 3, 8, 15, 25, 100], labels=["0-3", "4-8", "9-15", "16-25", "26+"])
old["ani"] = np.where(old.ftype.isin([1, 3]), "animation", "still")
old["hb"] = pd.cut(old.h, HB_EDGES, labels=HB_LABELS)
C["by_size"] = by(old, "px")
C["by_cls"] = sorted(by(old, "cls", CLS_NAME, 300), key=lambda x: -x["n"])
C["by_curation"] = by(old, "cur")
C["by_tier"] = by(old, "tier", min_n=1)
C["by_level"] = by(old, "lvl_band")
C["by_type"] = by(old, "ani")
C["block_by_human"] = [{"human": str(k), "n": int(len(d)), "mean_block": r(d.b.mean(), 2), "median_block": r(d.b.median(), 1),
                        "mean_human": r(d.h.mean(), 1), "reach_block": r((d.b > 0).mean()), "p10": r(d.b.quantile(.1), 1), "p90": r(d.b.quantile(.9), 1)}
                       for k, d in old.groupby("hb", observed=True)]
old["vb"] = pd.qcut(old.watch.rank(method="first"), 10, labels=False)
C["block_by_views"] = [{"decile": int(k), "views_lo": int(d.watch.min()), "views_hi": int(d.watch.max()), "mean_block": r(d.b.mean(), 2),
                        "mean_human": r(d.h.mean(), 2)} for k, d in old.groupby("vb")]
N["corr"] = {}
for k, d in rng.groupby("ab", observed=True):
    if len(d) > 500:
        N["corr"][str(k)] = {"n": int(len(d)), "block_vs_human": r(spearmanr(d.b, d.h).statistic), "block_vs_views": r(spearmanr(d.b, d.watch).statistic),
                             "human_vs_views": r(spearmanr(d.h, d.watch).statistic)}
N["corr"]["mature"] = {"n": int(len(old)), "block_vs_human": r(spearmanr(old.b, old.h).statistic),
                       "block_vs_views": r(spearmanr(old.b, old.watch).statistic), "human_vs_views": r(spearmanr(old.h, old.watch).statistic)}
# the same within one upload week, to kill any calendar effect
wk = old[(old.age_d >= 60) & (old.age_d < 67)]
N["corr"]["one_week_cohort"] = {"n": int(len(wk)), "block_vs_human": r(spearmanr(wk.b, wk.h).statistic)}

# log-log model: block likes ~ human likes ^ alpha, with the other factors as multipliers
X = pd.DataFrame({"const": 1.0, "log_h": np.log1p(old.h), "age_d": old.age_d / 30,
                  "master": (old.tier == "master").astype(float), "featured": (old.tier == "featured").astype(float),
                  "rec": old.rec.astype(float), "new": old.new.astype(float), "ani": (old.ani == "animation").astype(float),
                  "photo": old.photo.astype(float)})
for px in (32, 64, 128, 256):
    X[f"px{px}"] = (old.px == px).astype(float)
y = np.log1p(old.b.astype(float))
beta, *_ = np.linalg.lstsq(X.values, y.values, rcond=None)
pred = X.values @ beta


def r2(yv, pv):
    return r(1 - ((yv - pv) ** 2).sum() / ((yv - yv.mean()) ** 2).sum())


N["loglog"] = {"coef": {k: r(v, 3) for k, v in zip(X.columns, beta)}, "mult": {k: r(np.exp(v), 2) for k, v in zip(X.columns, beta) if k not in ("const", "log_h", "age_d")},
               "alpha": r(beta[1], 2), "r2": r2(y.values, pred)}
for name, cols in (("human_only", ["const", "log_h"]), ("no_human", [c for c in X.columns if c != "log_h"]), ("age_only", ["const", "age_d"])):
    bb_, *_ = np.linalg.lstsq(X[cols].values, y.values, rcond=None)
    N["loglog"]["r2_" + name] = r2(y.values, X[cols].values @ bb_)
# fitted curve block = f(human) for the chart
hh = np.array([0, 1, 2, 3, 5, 8, 12, 20, 35, 60, 100, 200, 400])
N["loglog"]["curve"] = [{"h": int(h), "b": r(np.expm1(beta[0] + beta[1] * np.log1p(h) + beta[2] * 3.0), 2)} for h in hh]
# median block likes by exact human count (small values), the empirical version
med = old[old.h <= 60].groupby("h").b.agg(med="median", avg="mean", cnt="size").reset_index()
C["block_vs_human_exact"] = [{"h": int(x.h), "median": r(x.med, 1), "mean": r(x.avg, 2), "n": int(x.cnt)} for x in med.itertuples() if x.cnt >= 30]

# tier x human-likes strata (the Master Pixel Artist question)
C["tier_by_human"] = [{"tier": tr, "human": str(hb), "n": int(len(d)), "mean_block": r(d.b.mean(), 2), "median_block": r(d.b.median(), 1)}
                      for (tr, hb), d in old.groupby(["tier", "hb"], observed=True) if len(d) >= 30]
C["cur_by_human"] = [{"cur": cu, "human": str(hb), "n": int(len(d)), "mean_block": r(d.b.mean(), 2)}
                     for (cu, hb), d in old.groupby(["cur", "hb"], observed=True) if len(d) >= 30]
C["tier_by_age"] = [{"tier": tr, "age": str(ab), "n": int(len(d)), "mean_block": r(d.b.mean(), 2), "mean_human": r(d.h.mean(), 2),
                     "reach_block": r((d.b > 0).mean())}
                    for (tr, ab), d in rng.groupby(["tier", "ab"], observed=True) if len(d) >= 20]
N["tiers"] = {}
for tr, d in old.groupby("tier"):
    N["tiers"][tr] = {"artworks": int(len(d)), "uploaders": int(d.uid.nunique()), "mean_block": r(d.b.mean(), 1), "median_block": r(d.b.median(), 1),
                      "mean_human": r(d.h.mean(), 1), "median_human": r(d.h.median(), 1), "mean_views": r(d.watch.mean(), 0),
                      "reach_block": r((d.b > 0).mean()), "block_share": r(d.b.sum() / max(d.n.sum(), 1)),
                      "p90_block": r(d.b.quantile(.9), 1), "ratio": r(d.b.sum() / d.h.sum(), 2),
                      "share_uploads": r(len(d) / len(old)), "share_block_likes": r(d.b.sum() / old.b.sum()), "share_human_likes": r(d.h.sum() / old.h.sum())}
# matched comparison: masters vs regulars at the same human-like band, weighted by the masters' band mix
mb = old[old.tier == "master"].groupby("hb", observed=True).b.agg(["mean", "size"])
rb = old[old.tier == "regular"].groupby("hb", observed=True).b.mean()
fb_ = old[old.tier == "featured"].groupby("hb", observed=True).b.mean()
w = mb["size"] / mb["size"].sum()
N["tiers"]["matched"] = {"master_mean": r((mb["mean"] * w).sum(), 1), "regular_at_same_popularity": r((rb.reindex(mb.index) * w).sum(), 1),
                         "featured_at_same_popularity": r((fb_.reindex(mb.index) * w).sum(), 1)}
mu = old[old.tier == "master"].groupby("uid").agg(n=("gid", "size"), b=("b", "mean"), h=("h", "mean"), lvl=("level", "first")).reset_index()
mu = mu[mu.n >= 5]
C["masters"] = [{"arts": int(x.n), "mean_block": r(x.b, 1), "mean_human": r(x.h, 1), "level": int(x.lvl)} for x in mu.sort_values("h").itertuples()]
N["masters_spread"] = {"uploaders": int(len(mu)), "min_mean_block": r(mu.b.min(), 1), "max_mean_block": r(mu.b.max(), 1),
                       "min_mean_human": r(mu.h.min(), 1), "max_mean_human": r(mu.h.max(), 1), "corr": r(spearmanr(mu.b, mu.h).statistic)}
ru = old[old.tier == "regular"].groupby("uid").agg(n=("gid", "size"), b=("b", "mean"), h=("h", "mean")).reset_index()
ru = ru[ru.n >= 5]
C["regular_uploaders"] = [{"mean_block": r(x.b, 1), "mean_human": r(x.h, 1)} for x in ru.sample(min(len(ru), 1500), random_state=1).itertuples()]
N["regular_uploaders_spread"] = {"uploaders": int(len(ru)), "p10": r(ru.b.quantile(.1), 1), "p50": r(ru.b.quantile(.5), 1), "p90": r(ru.b.quantile(.9), 1),
                                 "corr": r(spearmanr(ru.b, ru.h).statistic)}

# --------------------------------------------------------------------------- C. timing (hourly pulse events)
pu = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(str(RAW / "pulse/**/*-likes.parquet"), recursive=True))], ignore_index=True)
pu = pu.sort_values("t").drop_duplicates(["gid", "liker"], keep="first")
pu["blk"] = is_block(pu.liker)
ch = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(str(RAW / "pulse/**/*-changes.parquet"), recursive=True))], ignore_index=True)
meta = ch.drop_duplicates("gid").set_index("gid")[["uid", "date", "cls", "size"]]
extra = cat.set_index("gid")[["uid", "date", "cls", "size"]]
meta = pd.concat([meta, extra[~extra.index.isin(meta.index)]])
pu = pu.join(meta, on="gid")
pu = pu[pu.date.notna()].copy()
pu["lo"] = np.maximum(pu.date, pu.t_prev)
pu["width_h"] = (pu.t - pu.lo) / 3600
pu["mid"] = (pu.lo + pu.t) / 2
pulse_t = np.array(sorted(ch.t.unique()))
gaps = np.diff(pulse_t) / 3600
N["ev"] = {"from": "2026-10-05", "to": "2026-11-03", "likes": int(len(pu)), "block": int(pu.blk.sum()), "block_share": r(pu.blk.mean()),
           "artworks": int(pu.gid.nunique()), "pulses": int(len(pulse_t)), "hours_spanned": int((pulse_t[-1] - pulse_t[0]) / 3600),
           "gaps_over_2h": int((gaps > 2).sum()), "longest_gap_h": r(gaps.max(), 0), "within_2h_share": r((pu.width_h <= 2.5).mean()),
           "median_width_h": r(pu.width_h.median(), 2)}
fresh = pu[pu.date >= T0].copy()
fresh["tier"] = tier_of(fresh.uid)
fresh["age_h"] = (fresh.mid - fresh.date) / 3600
N["ev"]["fresh_artworks"] = int(fresh.gid.nunique())
N["ev"]["fresh_block"] = int(fresh.blk.sum())
N["ev"]["fresh_human"] = int((~fresh.blk).sum())
N["ev"]["fresh_block_share"] = r(fresh.blk.mean())

# C1 first block like vs first human like (artworks uploaded at least 7 days before the end)
upl_all = cat[(cat.date >= T0) & (cat.date <= T1 - 7 * DAY)][["gid", "uid", "date"]].copy()
upl_all["tier"] = tier_of(upl_all.uid)
up = fresh[fresh.date <= T1 - 7 * DAY]
fb = (up[up.blk].groupby("gid").t.min() - up[up.blk].groupby("gid").date.first())
fh = (up[~up.blk].groupby("gid").t.min() - up[~up.blk].groupby("gid").date.first())
n_up = len(upl_all)
qs = [.1, .25, .5, .75, .9]
N["first_like"] = {"artworks_7d": int(n_up), "with_block_like_7d": int(len(fb)), "with_human_like_7d": int(len(fh)),
                   "reach_block_7d": r(len(fb) / n_up), "reach_human_7d": r(len(fh) / n_up),
                   "block_hours_q": {str(q): r(fb.quantile(q) / 3600, 1) for q in qs},
                   "human_hours_q": {str(q): r(fh.quantile(q) / 3600, 1) for q in qs},
                   "block_within_1h": r((fb <= 3600).mean()), "block_within_6h": r((fb <= 6 * 3600).mean()),
                   "block_within_24h": r((fb <= DAY).mean()), "block_within_72h": r((fb <= 3 * DAY).mean()),
                   "human_within_1h": r((fh <= 3600).mean()), "human_within_6h": r((fh <= 6 * 3600).mean()), "human_within_24h": r((fh <= DAY).mean())}
hrs = [1, 2, 3, 6, 9, 12, 18, 24, 36, 48, 72, 96, 120, 168]
C["first_like_cdf"] = [{"h": h, "block": r(len(fb[fb <= h * 3600]) / n_up), "human": r(len(fh[fh <= h * 3600]) / n_up)} for h in hrs]
# does the first block like wait for the first human like? order of the two on the same artwork
both = pd.concat([fb.rename("b"), fh.rename("h")], axis=1).dropna()
N["first_like"]["artworks_with_both"] = int(len(both))
N["first_like"]["human_first_share"] = r((both.h < both.b).mean())
N["first_like"]["same_hour_share"] = r((both.h == both.b).mean())
N["first_like"]["block_only_7d"] = int(len(fb.index.difference(fh.index)))
N["first_like"]["human_only_7d"] = int(len(fh.index.difference(fb.index)))
N["first_like_by_tier"] = {}
for tr in ("master", "featured", "regular"):
    gids = set(upl_all[upl_all.tier == tr].gid)
    f1 = fb[fb.index.isin(gids)]
    h1 = fh[fh.index.isin(gids)]
    N["first_like_by_tier"][tr] = {"artworks": len(gids), "reached_7d": r(len(f1) / max(len(gids), 1)), "human_reached_7d": r(len(h1) / max(len(gids), 1)),
                                   "median_h": r(f1.median() / 3600, 1), "q25_h": r(f1.quantile(.25) / 3600, 1), "q75_h": r(f1.quantile(.75) / 3600, 1),
                                   "human_median_h": r(h1.median() / 3600, 1), "within_24h": r((f1 <= DAY).mean())}

# C2 like rate per artwork per day of age, block vs human (reliable to about two weeks: the hourly crawl reaches that deep)
ups = cat[(cat.date >= T0) & (cat.date <= T1)][["gid", "date"]].copy()
ups["exp_d"] = (T1 - ups.date) / DAY
fresh["ad"] = fresh.age_h // 24
rate = fresh.groupby(["ad", "blk"]).size().unstack(fill_value=0)
C["rate_by_age"] = [{"d": d, "exposed": int((ups.exp_d >= d + 1).sum()),
                     "block": r(rate.loc[d, True] / (ups.exp_d >= d + 1).sum(), 3) if d in rate.index else 0,
                     "human": r(rate.loc[d, False] / (ups.exp_d >= d + 1).sum(), 3) if d in rate.index else 0} for d in range(0, 14)]
fresh["ah"] = fresh.age_h.astype(int)
ups["exp_h"] = (T1 - ups.date) / 3600
rate_h = fresh[fresh.ah < 96].groupby(["ah", "blk"]).size().unstack(fill_value=0)
C["rate_by_hour"] = [{"h": h, "block": r(rate_h.loc[h, True] / (ups.exp_h >= h + 1).sum(), 4) if h in rate_h.index else 0,
                      "human": r(rate_h.loc[h, False] / (ups.exp_h >= h + 1).sum(), 4) if h in rate_h.index else 0} for h in range(0, 96)]
tot_b = sum(x["block"] for x in C["rate_by_age"])
N["rate"] = {"block_first_day": C["rate_by_age"][0]["block"], "human_first_day": C["rate_by_age"][0]["human"],
             "block_day2": C["rate_by_age"][1]["block"], "block_week2_per_day": r(np.mean([x["block"] for x in C["rate_by_age"][7:14]]), 3),
             "block_14d_total": r(tot_b, 2), "human_14d_total": r(sum(x["human"] for x in C["rate_by_age"]), 2),
             "block_share_first6h": r(sum(x["block"] for x in C["rate_by_hour"][:6]) / max(sum(x["block"] + x["human"] for x in C["rate_by_hour"][:6]), 1e-9)),
             "block_share_day2": r(C["rate_by_age"][1]["block"] / (C["rate_by_age"][1]["block"] + C["rate_by_age"][1]["human"])),
             "block_share_week2": r(sum(x["block"] for x in C["rate_by_age"][7:14]) / sum(x["block"] + x["human"] for x in C["rate_by_age"][7:14]))}

# C3 clock: hour of day and weekday of likes dated to within about an hour, per pulse that covered that hour
sharp = pu[(pu.width_h <= 2.5)].copy()
sharp["hour_utc"] = ((sharp.mid // 3600) % 24).astype(int)
sharp["dow"] = pd.to_datetime(sharp.mid, unit="s").dt.dayofweek
cov = pd.Series(((pulse_t - 1800) // 3600) % 24).value_counts().reindex(range(24), fill_value=0)
hod = sharp.groupby(["hour_utc", "blk"]).size().unstack(fill_value=0).reindex(range(24), fill_value=0)
C["hour_of_day"] = [{"h": h, "block": r(hod.loc[h, True] / max(cov[h], 1), 1), "human": r(hod.loc[h, False] / max(cov[h], 1), 1), "pulses": int(cov[h])} for h in range(24)]
dow = sharp.groupby(["dow", "blk"]).size().unstack(fill_value=0).reindex(range(7), fill_value=0)
covd = pd.Series(pd.to_datetime(pulse_t - 1800, unit="s").dayofweek).value_counts().reindex(range(7), fill_value=0)
C["day_of_week"] = [{"d": d, "block": r(dow.loc[d, True] / max(covd[d], 1), 1), "human": r(dow.loc[d, False] / max(covd[d], 1), 1)} for d in range(7)]
hb_ = C["hour_of_day"]
bmax, bmin = max(hb_, key=lambda x: x["block"]), min(hb_, key=lambda x: x["block"])
hmax, hmin = max(hb_, key=lambda x: x["human"]), min(hb_, key=lambda x: x["human"])
N["clock"] = {"sharp_likes": int(len(sharp)), "sharp_block": int(sharp.blk.sum()),
              "block_hour_max": bmax["h"], "block_hour_min": bmin["h"], "block_max_over_min": r(bmax["block"] / max(bmin["block"], .01), 2),
              "human_hour_max": hmax["h"], "human_hour_min": hmin["h"], "human_max_over_min": r(hmax["human"] / max(hmin["human"], .01), 2),
              "block_cv_hours": r(np.std([x["block"] for x in hb_]) / np.mean([x["block"] for x in hb_]), 2),
              "human_cv_hours": r(np.std([x["human"] for x in hb_]) / np.mean([x["human"] for x in hb_]), 2),
              "block_cv_days": r(np.std([x["block"] for x in C["day_of_week"]]) / np.mean([x["block"] for x in C["day_of_week"]]), 2),
              "human_cv_days": r(np.std([x["human"] for x in C["day_of_week"]]) / np.mean([x["human"] for x in C["day_of_week"]]), 2)}
# the month as an hourly series (block and human likes dated to within an hour, per pulse hour)
ser = sharp.groupby([(sharp.t // 3600) * 3600, "blk"]).size().unstack(fill_value=0)
ser = ser.reindex(range(int(pulse_t[0] // 3600 * 3600), int(pulse_t[-1] // 3600 * 3600) + 3600, 3600))
covered = pd.Series(pulse_t // 3600 * 3600).value_counts()
C["hourly_series"] = [{"t": int(t), "block": (int(x[True]) if not np.isnan(x[True]) else None) if t in covered.index else None,
                       "human": (int(x[False]) if not np.isnan(x[False]) else None) if t in covered.index else None} for t, x in ser.iterrows()]
# block likes per artwork within one hour, and gaps between consecutive block likes on one artwork
bl = fresh[fresh.blk & (fresh.width_h <= 2.5)]
per_hour = bl.groupby(["gid", "t"]).size()
hl = fresh[~fresh.blk & (fresh.width_h <= 2.5)]
per_hour_h = hl.groupby(["gid", "t"]).size()
C["likes_per_hour_dist"] = [{"k": int(k) if k < 5 else "5+", "block": r(per_hour.clip(upper=5).value_counts(normalize=True).get(k, 0)),
                             "human": r(per_hour_h.clip(upper=5).value_counts(normalize=True).get(k, 0))} for k in range(1, 6)]
N["per_hour"] = {"block_mean": r(per_hour.mean(), 2), "block_share_1": r((per_hour == 1).mean()), "human_mean": r(per_hour_h.mean(), 2), "human_share_1": r((per_hour_h == 1).mean())}
bl_s = bl.sort_values(["gid", "t"])
gap = bl_s.groupby("gid").t.diff().dropna() / 3600
hl_s = hl.sort_values(["gid", "t"])
gaph = hl_s.groupby("gid").t.diff().dropna() / 3600
N["gaps"] = {"block_median_h": r(gap.median(), 1), "block_q25_h": r(gap.quantile(.25), 1), "block_q75_h": r(gap.quantile(.75), 1),
             "block_share_le1h": r((gap <= 1.5).mean()), "human_median_h": r(gaph.median(), 1), "human_share_le1h": r((gaph <= 1.5).mean())}
C["gap_dist"] = [{"h": h, "block": r((gap.clip(upper=48) // 1 == h).mean()), "human": r((gaph.clip(upper=48) // 1 == h).mean())} for h in range(0, 49)]
f7 = fresh[fresh.blk & (fresh.age_h < 7 * 24) & (fresh.date <= T1 - 7 * DAY)]
visits = f7.groupby("gid").t.nunique()
N["visits_7d"] = {"artworks": int(len(visits)), "mean_hours_with_block_like": r(visits.mean(), 2), "median": r(visits.median(), 1),
                  "mean_block_likes_7d": r(f7.groupby("gid").size().mean(), 2)}

# C4 does the block follow the humans hour by hour? artwork x hour panel of fresh artworks, lagged correlations
pan = fresh[fresh.width_h <= 2.5].groupby(["gid", "t", "blk"]).size().unstack(fill_value=0).rename(columns={True: "b", False: "h"}).reset_index()
chf = ch[ch.gid.isin(fresh.gid.unique())].sort_values(["gid", "t"]).copy()
chf["dv"] = chf.groupby("gid").watch.diff().fillna(0).clip(lower=0)
chf["dl"] = chf.groupby("gid").like.diff().fillna(0).clip(lower=0)
pan = chf[["gid", "t", "dv", "dl"]].merge(pan, on=["gid", "t"], how="left").fillna({"b": 0, "h": 0})
pan = pan.sort_values(["gid", "t"])
# a balanced hourly grid per artwork is not available (artworks are read only when listed), so use consecutive reads
for L in (1, 2, 3):
    pan[f"h_m{L}"] = pan.groupby("gid").h.shift(L)
    pan[f"b_m{L}"] = pan.groupby("gid").b.shift(L)
    pan[f"v_m{L}"] = pan.groupby("gid").dv.shift(L)
pan["h_p1"] = pan.groupby("gid").h.shift(-1)
pan["v_p1"] = pan.groupby("gid").dv.shift(-1)
pan["b_p1"] = pan.groupby("gid").b.shift(-1)
sub = pan.dropna(subset=["h_m1", "b_m1", "h_p1"])
N["lag"] = {"rows": int(len(sub)), "artworks": int(sub.gid.nunique())}
for a, b_ in (("b", "h"), ("b", "h_m1"), ("b", "h_m2"), ("b", "h_m3"), ("b", "h_p1"), ("b", "dv"), ("b", "v_m1"), ("b", "v_p1"), ("b", "b_m1"),
              ("h", "h_m1"), ("h", "b_m1"), ("h", "v_m1"), ("h", "dv")):
    N["lag"][f"{a}~{b_}"] = r(spearmanr(sub[a], sub[b_]).statistic)
# conditional rates: chance of a block like this hour given humans liked in the previous hour (or not)
N["lag"]["p_block_given_human_prev"] = r((sub[sub.h_m1 > 0].b > 0).mean())
N["lag"]["p_block_given_no_human_prev"] = r((sub[sub.h_m1 == 0].b > 0).mean())
N["lag"]["p_block_given_views_prev"] = r((sub[sub.v_m1 > 0].b > 0).mean())
N["lag"]["p_block_given_no_views_prev"] = r((sub[sub.v_m1 == 0].b > 0).mean())
N["lag"]["p_human_given_block_prev"] = r((sub[sub.b_m1 > 0].h > 0).mean())
N["lag"]["p_human_given_no_block_prev"] = r((sub[sub.b_m1 == 0].h > 0).mean())
N["lag"]["p_block_given_block_prev"] = r((sub[sub.b_m1 > 0].b > 0).mean())
N["lag"]["p_block_given_no_block_prev"] = r((sub[sub.b_m1 == 0].b > 0).mean())
N["lag"]["p_block"] = r((sub.b > 0).mean())
N["lag"]["p_human"] = r((sub.h > 0).mean())
# views bands within the hour: block like chance vs how many views the artwork got in that same read
sub2 = pan.copy()
sub2["vb"] = pd.cut(sub2.dv, [-1, 0, 2, 5, 10, 20, 50, 10 ** 7], labels=["0", "1-2", "3-5", "6-10", "11-20", "21-50", "50+"])
C["block_by_views_hour"] = [{"views": str(k), "n": int(len(d)), "p_block": r((d.b > 0).mean()), "p_human": r((d.h > 0).mean()), "mean_block": r(d.b.mean(), 3), "mean_human": r(d.h.mean(), 3)}
                            for k, d in sub2.groupby("vb", observed=True)]
# early popularity -> later block likes: human likes in first 6 h vs block likes in hours 6-72
e6 = fresh[fresh.age_h < 6].groupby(["gid", "blk"]).size().unstack(fill_value=0).rename(columns={True: "b6", False: "h6"})
l72 = fresh[(fresh.age_h >= 6) & (fresh.age_h < 72)].groupby(["gid", "blk"]).size().unstack(fill_value=0).rename(columns={True: "b72", False: "h72"})
early = upl_all.set_index("gid").join(e6).join(l72).fillna(0)
early = early[early.date <= T1 - 3 * DAY]
early["h6b"] = pd.cut(early.h6, [-1, 0, 1, 2, 4, 8, 10 ** 6], labels=["0", "1", "2", "3-4", "5-8", "9+"])
C["early_human_later_block"] = [{"human_6h": str(k), "n": int(len(d)), "block_6_72h": r(d.b72.mean(), 2), "human_6_72h": r(d.h72.mean(), 2), "reach_block": r((d.b72 > 0).mean())}
                                for k, d in early.groupby("h6b", observed=True)]
N["early"] = {"corr_h6_b72": r(spearmanr(early.h6, early.b72).statistic), "corr_b6_h72": r(spearmanr(early.b6, early.h72).statistic),
              "corr_h6_h72": r(spearmanr(early.h6, early.h72).statistic), "n": int(len(early))}

# C5 the trickle on old artworks (snapshot reads every two days of artworks older than 30 days whose counter rose)
sn = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(str(RAW / "snapshot/**/likes.parquet"), recursive=True))], ignore_index=True)
sn = sn.drop_duplicates(["gid", "liker"])
sn["blk"] = is_block(sn.liker)
sn = sn.join(cat.set_index("gid")[["uid", "date"]], on="gid")
sn = sn[sn.date.notna()]
sn["age_y"] = (sn.t - sn.date) / (365 * DAY)
sn["ab"] = pd.cut(sn.age_y, [0, .25, .5, 1, 2, 3, 5, 10], labels=["1-3 m", "3-6 m", "6-12 m", "1-2 y", "2-3 y", "3-5 y", "5+ y"])
N["trickle"] = {"likes": int(len(sn)), "block": int(sn.blk.sum()), "block_share": r(sn.blk.mean()), "artworks": int(sn.gid.nunique())}
C["trickle_by_age"] = [{"age": str(k), "likes": int(len(d)), "block_share": r(d.blk.mean()), "artworks": int(d.gid.nunique())} for k, d in sn.groupby("ab", observed=True)]
# rate of the trickle: total like growth of old public artworks from the full-catalog snapshot crawl, per artwork per day, by age
snc = pd.concat([pd.read_parquet(f, columns=["gid", "date", "like", "t"]) for f in sorted(glob.glob(str(RAW / "snapshot/**/changes-*.parquet"), recursive=True))], ignore_index=True)
snc = snc.sort_values(["gid", "t"])
snc["dl"] = snc.groupby("gid").like.diff()
snc["dt"] = snc.groupby("gid").t.diff()
g2 = snc.dropna(subset=["dl"])
g2 = g2[(g2.dt > 0) & (g2.dl >= 0)]
g2["age_y"] = (g2.t - g2.date) / (365 * DAY)
g2["ab"] = pd.cut(g2.age_y, [0, .25, .5, 1, 2, 3, 5, 10], labels=["1-3 m", "3-6 m", "6-12 m", "1-2 y", "2-3 y", "3-5 y", "5+ y"])
tr_ = g2.groupby("ab", observed=True).agg(dl=("dl", "sum"), dt=("dt", "sum"), n=("gid", "nunique"))
tr_["per_art_year"] = tr_.dl / (tr_.dt / (365 * DAY))
C["trickle_rate"] = [{"age": str(k), "artworks": int(x.n), "likes_per_artwork_year": r(x.per_art_year, 2)} for k, x in tr_.iterrows()]
N["trickle"]["catalog_pairs"] = int(len(g2))

# --------------------------------------------------------------------------- D. the accounts (brief)
pa = bf[bf.blk].groupby("liker").size()
N["accounts"] = {"seen": int(len(pa)), "mean": r(pa.mean(), 1), "min": int(pa.min()), "max": int(pa.max()), "sd": r(pa.std(), 1),
                 "cv": r(pa.std() / pa.mean()), "poisson_cv": r(1 / np.sqrt(pa.mean())), "top20_share": r(pa.sort_values(ascending=False).head(20).sum() / pa.sum())}
hp = bf[~bf.blk].groupby("liker").size()
N["accounts"]["human_likers"] = int(len(hp))
N["accounts"]["human_top1pct_share"] = r(hp.sort_values(ascending=False).head(max(len(hp) // 100, 1)).sum() / hp.sum())
N["accounts"]["human_median"] = r(hp.median(), 0)
N["accounts"]["human_max"] = int(hp.max())
bb = bf[bf.blk].merge(cat[["gid", "uid"]], on="gid")
k = bb.groupby(["liker", "uid"]).size()
N["accounts"]["share_repeat_uploader"] = r((k[k > 1].sum() - (k > 1).sum()) / k.sum())
sim = np.random.default_rng(0).integers(0, 2000, size=len(bb))
k2 = pd.Series(1, index=pd.MultiIndex.from_arrays([sim, bb.uid.values])).groupby(level=[0, 1]).size()
N["accounts"]["share_repeat_uploader_if_random"] = r((k2[k2 > 1].sum() - (k2 > 1).sum()) / k2.sum())
C["account_dist"] = [{"likes": int(a), "accounts": int(b_)} for a, b_ in pa.value_counts().sort_index().items()]
# consecutive block likes on one artwork: are the account ids related?
bs = bf[bf.blk].sort_values(["gid", "pos"])
d_ = bs.groupby("gid").liker.diff().dropna().abs()
N["accounts"]["consecutive_same_account_share"] = r((d_ == 0).mean())
N["accounts"]["consecutive_within_10_ids_share"] = r((d_ <= 20).mean())
N["accounts"]["consecutive_within_10_ids_if_random"] = r(min(1.0, 20 / 4000 * 2))

# --------------------------------------------------------------------------- E. uploaders' side
upl = rng.groupby("uid").agg(arts=("gid", "size"), b=("b", "sum"), h=("h", "sum")).reset_index()
N["uploaders"] = {"n": int(len(upl)), "block_top10pct_share": r(upl.b.sort_values(ascending=False).head(len(upl) // 10).sum() / upl.b.sum()),
                  "human_top10pct_share": r(upl.h.sort_values(ascending=False).head(len(upl) // 10).sum() / upl.h.sum()),
                  "arts_top10pct_share": r(upl.arts.sort_values(ascending=False).head(len(upl) // 10).sum() / upl.arts.sum()),
                  "block_bottom50pct_share": r(upl.b.sort_values().head(len(upl) // 2).sum() / upl.b.sum()),
                  "human_bottom50pct_share": r(upl.h.sort_values().head(len(upl) // 2).sum() / upl.h.sum()),
                  "uploaders_no_block_like": r((upl.b == 0).mean()), "uploaders_no_human_like": r((upl.h == 0).mean())}

json.dump(N, open(OUT / "numbers.json", "w"), indent=1)
json.dump(C, open(OUT / "charts.json", "w"), indent=0)
print(json.dumps(N, indent=1))
