"""Request 04: the 20 newest uploads of ThePixelXḃ_ (UserId 400791502).

Run from python/:  python ../requests/04-thepixelxb/fetch.py
Raw files land in requests/04-thepixelxb/downloads/ (git-ignored), decoded images in out/.
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "python"))

from credentials import TEST_ACCOUNTS  # noqa: E402
from servoom import DivoomClient  # noqa: E402
from servoom.const import GallerySize, GallerySort  # noqa: E402
from servoom.layer_file_decoder import LayerFileDecoder  # noqa: E402
from servoom.pixel_bean_decoder import PixelBeanDecoder  # noqa: E402

USER_ID = 400791502
N = 20
DL = HERE / "downloads"
OUT = HERE / "out"

acct = TEST_ACCOUNTS["test_01"]
c = DivoomClient(email=acct["email"], md5_password=acct["md5"])
assert c.login(), "login failed"

info = c.fetch_someone_info(USER_ID)
print("profile:", json.dumps({k: info.get(k) for k in ("UserId", "NickName", "Level", "FansCnt", "GalleryCnt")}, ensure_ascii=False))

arts = c.fetch_someone_arts(USER_ID, limit=60, FileSort=GallerySort.LATEST, FileSize=GallerySize.ALL)
arts.sort(key=lambda a: a.get("Date", 0), reverse=True)
arts = arts[:N]
print(f"{len(arts)} newest uploads:")
for a in arts:
    print(f"  {a['GalleryId']}  date={a.get('Date')}  {a.get('FileName')!r}  layer={'yes' if a.get('LayerFileId') else 'no'}  music={'yes' if a.get('MusicFileId') else 'no'}")
(HERE / "listing.json").write_text(json.dumps(arts, ensure_ascii=False, indent=1), encoding="utf-8")

DL.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)
results = []
for a in arts:
    gid = a["GalleryId"]
    bean, dat = c.download_art_by_id(gid, str(DL))
    row = {"gallery_id": gid, "name": a.get("FileName"), "dat": os.path.basename(dat)}
    b = PixelBeanDecoder.decode_file(dat)
    if b is None:
        row["webp"] = None
    else:
        webp = OUT / f"{gid}.webp"
        b.save_to_webp(str(webp))
        row.update(webp=webp.name, frames=b.total_frames, size=f"{b.width}x{b.height}")
    if a.get("LayerFileId"):
        lpath = DL / f"{gid}_layer.dat"
        c.download_file(a["LayerFileId"], str(lpath))
        layer = LayerFileDecoder.decode_file(str(lpath))
        layer.save_to_webp(str(OUT / f"{gid}_layer.webp"))
        layer.save_to_psd(str(OUT / f"{gid}_layer.psd"))
        row.update(layer_frames=layer.num_frames, layers=layer.total_layers)
    print(row)
    results.append(row)
(HERE / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
