"""For each bot artwork that shares its upload second with a regular user's artwork,
fetch both (GalleryInfo + file), compare FileIds, decode first frames to PNG (out/pairs/)."""
import glob, json, sys, time
from pathlib import Path
import pandas as pd, pyarrow.parquet as pq
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]; RAW = ROOT.parent / "servoom-raw"
sys.path.insert(0, str(ROOT / "python"))
from servoom.client import DivoomClient
from servoom.pixel_bean_decoder import PixelBeanDecoder
from credentials import TEST_ACCOUNTS
BLOCK = (400971852, 400975850)
a = TEST_ACCOUNTS["bots_check_01"]
c = DivoomClient(email=a["email"], md5_password=a["md5"]); assert c.login()
chg = pd.concat([pq.read_table(f).to_pandas() for f in glob.glob(str(RAW / "obs/snapshot/**/changes-*.parquet"), recursive=True)])
chg = chg.sort_values("t").drop_duplicates("gid", keep="last")
outdir = HERE / "out" / "pairs"; outdir.mkdir(parents=True, exist_ok=True)
dl = HERE / "out" / "dl"; dl.mkdir(exist_ok=True)

def grab(gid):
    info = c.fetch_artwork_info(gid)
    if not info: return None, None
    try:
        bean, path = c.download_art_by_id(gid, output_dir=str(dl))
        c.decode_art(bean)
        img = bean.get_frame_image(1, scale=8)
        png = outdir / f"{gid}.png"; img.save(png)
        return info, {"png": png.name, "frames": bean.total_frames, "w": bean.width, "h": bean.height}
    except Exception as exc:
        return info, {"error": str(exc)}

pairs = []
for uid, name in ((400973210, "julycat"), (400975304, "Drew")):
    ev = json.loads((HERE / "out" / f"evidence_{uid}.json").read_text(encoding="utf-8"))
    for r in ev["artworks"]["list"]:
        if not r["same_date_nonblock_owners"]: continue
        orig = chg[(chg.date == r["Date"]) & (chg.uid.isin(r["same_date_nonblock_owners"]))]
        binfo, bimg = grab(r["GalleryId"]); time.sleep(0.4)
        for _, o in orig.iterrows():
            oinfo, oimg = grab(int(o.gid)); time.sleep(0.4)
            if not oinfo: continue
            pairs.append({"bot": name, "bot_uid": uid, "bot_gid": r["GalleryId"], "bot_file": binfo.get("FileId"), "bot_date": binfo.get("Date"),
                          "bot_title": binfo.get("FileName"), "bot_img": bimg,
                          "orig_gid": int(o.gid), "orig_uid": int(o.uid), "orig_file": oinfo.get("FileId"), "orig_date": oinfo.get("Date"),
                          "orig_title": oinfo.get("FileName"), "orig_level": oinfo.get("Level"), "orig_img": oimg,
                          "same_file": binfo.get("FileId") == oinfo.get("FileId")})
            p = pairs[-1]; print(name, p["bot_gid"], "<->", p["orig_gid"], "same_file", p["same_file"], p["bot_title"], "|", p["orig_title"], flush=True)
(HERE / "out" / "pairs.json").write_text(json.dumps(pairs, indent=1, ensure_ascii=False), encoding="utf-8")
print(len(pairs), "pairs;", sum(p["same_file"] for p in pairs), "same file")
