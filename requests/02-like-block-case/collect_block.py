"""One-off snapshot of the 2,000 like-block accounts with the bots_check_01 account:
avatar file (decoded first frame -> out/avatars/<uid>.png, 16x16 raw kept as .raw) and the
full public artwork list (out/block_arts.jsonl). Resumable. Read-only."""
import json, sys, time, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np, requests
from PIL import Image
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "python"))
from servoom.client import DivoomClient
from servoom.pixel_bean_decoder import PixelBeanDecoder
from credentials import TEST_ACCOUNTS
OUT = HERE / "out"; AV = OUT / "avatars"; AV.mkdir(parents=True, exist_ok=True)
profiles = [json.loads(l) for l in (ROOT / "requests/01-check-divoom-accounts-bots/out/block_profiles.jsonl").open(encoding="utf-8")]
a = TEST_ACCOUNTS["bots_check_01"]
c = DivoomClient(email=a["email"], md5_password=a["md5"]); assert c.login()
arts_path = OUT / "block_arts.jsonl"
done = set()
if arts_path.exists():
    for l in arts_path.open(encoding="utf-8"): done.add(json.loads(l)["uid"])
lock = threading.Lock(); fh = arts_path.open("a", encoding="utf-8")
sess = requests.Session()
def avatar(uid, head):
    png = AV / f"{uid}.png"
    if png.exists() or not head: return "skip"
    try:
        r = sess.get(f"https://f.divoom-gz.com/{head}", timeout=30); r.raise_for_status()
        raw = AV / f"{uid}.dat"; raw.write_bytes(r.content)
        bean = PixelBeanDecoder.decode_file(str(raw))
        if bean is None: return "undecodable"
        im = bean.get_frame_image(1)
        im.save(png); raw.unlink()
        return f"{im.width}x{im.height}x{bean.total_frames}"
    except Exception as exc:
        return f"err {exc}"
KEEP = ("GalleryId", "FileId", "FileName", "Date", "LikeCnt", "WatchCnt", "CommentCnt", "FileType", "FileSize", "Classify", "PrivateFlag", "IsDel")
def one(p):
    uid = p["uid"]
    av = avatar(uid, p.get("HeadId"))
    if uid in done: return
    arts = None
    for _ in range(3):
        try:
            arts = c.fetch_someone_arts(uid, limit=None); break
        except Exception: time.sleep(3)
    row = {"uid": uid, "avatar": av, "arts": [{k: x.get(k) for k in KEEP} for x in (arts or [])] if arts is not None else None}
    with lock:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n"); fh.flush()
    time.sleep(0.5)
with ThreadPoolExecutor(4) as ex:
    for i, _ in enumerate(ex.map(one, profiles)):
        if i % 100 == 0: print("progress", i, flush=True)
print("done")
