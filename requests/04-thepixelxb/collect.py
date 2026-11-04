"""Collect every upload of ThePixelXḃ_ (UserId 400791502) with layer files, likes, comments.

Run from python/:  python ../requests/04-thepixelxb/collect.py
Resumable: artworks whose folder holds a complete metadata.json are skipped.
Paced to the Divoom limit of 30 API requests per sliding minute.
"""
import datetime as dt
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "python"))

from credentials import TEST_ACCOUNTS  # noqa: E402
from servoom import DivoomClient  # noqa: E402
from servoom.config import Settings  # noqa: E402
from servoom.const import GallerySize, GallerySort  # noqa: E402
from servoom.util import sanitize_filename  # noqa: E402

USER_ID = 400791502
PKG = HERE / "package"
ARTS = PKG / "artworks"
GAP = 2.05  # seconds between API calls -> under 30 per minute

acct = TEST_ACCOUNTS["test_01"]
c = DivoomClient(email=acct["email"], md5_password=acct["md5"], settings=Settings(batch_size=100))

# pace + retry every API call
_orig = c._session.post_json
_last = [0.0]
def paced(path, payload=None):
    for attempt in range(6):
        wait = GAP - (time.monotonic() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.monotonic()
        try:
            resp = _orig(path, payload)
        except Exception as exc:  # non-JSON (e.g. HTTP 429) or transport failure
            print(f"  ! {path}: {exc!r}; sleeping 70 s", flush=True)
            time.sleep(70)
            continue
        if resp.get("ReturnCode") == 12:
            if attempt >= 1:  # same answer after a full minute: depth cap, not rate limit
                print(f"  ! {path}: ReturnCode 12 persists at {payload.get('StartNum')}; treating as end of list", flush=True)
                return resp
            print(f"  ! {path}: ReturnCode 12 (rate limit or depth cap); sleeping 70 s", flush=True)
            time.sleep(70)
            continue
        return resp
    raise RuntimeError(f"gave up on {path}")
c._session.post_json = paced

def retry(fn, *args, tries=5):
    for attempt in range(tries):
        try:
            return fn(*args)
        except Exception as exc:
            if "404" in str(exc):
                print(f"  ! file missing on server (404): {args[0]}", flush=True)
                return None
            print(f"  ! download failed ({exc}); retry {attempt + 1}/{tries} after 30 s", flush=True)
            time.sleep(30)
    raise RuntimeError("download kept failing")

assert c.login(), "login failed"
PKG.mkdir(exist_ok=True); ARTS.mkdir(exist_ok=True)

if not (PKG / "profile.json").exists():
  profile = c.fetch_someone_info(USER_ID)
  (PKG / "profile.json").write_text(json.dumps(profile, ensure_ascii=False, indent=1), encoding="utf-8")
  medals = c.fetch_user_medals(USER_ID)
  (PKG / "medals.json").write_text(json.dumps(medals, ensure_ascii=False, indent=1), encoding="utf-8")

lst = PKG / "listing.json"
arts = json.loads(lst.read_text(encoding="utf-8")) if lst.exists() else     c.fetch_someone_arts(USER_ID, FileSort=GallerySort.LATEST, FileSize=GallerySize.ALL)
arts.sort(key=lambda a: a.get("Date", 0), reverse=True)
(PKG / "listing.json").write_text(json.dumps(arts, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(arts)} uploads listed", flush=True)

def folder_for(a):
    day = dt.datetime.fromtimestamp(a["Date"], dt.timezone.utc).strftime("%Y-%m-%d")
    raw = "".join(ch if ch.isprintable() else " " for ch in (a.get("FileName") or "untitled"))
    name = sanitize_filename(" ".join(raw.split()), 60).strip() or "untitled"
    return ARTS / f"{day}_{a['GalleryId']}_{name}"

for i, a in enumerate(arts, 1):
    gid = a["GalleryId"]
    d = folder_for(a)
    meta_path = d / "metadata.json"
    if meta_path.exists() and json.loads(meta_path.read_text(encoding="utf-8")).get("complete"):
        continue
    d.mkdir(parents=True, exist_ok=True)
    print(f"[{i}/{len(arts)}] {gid} {d.name}", flush=True)
    likes = c.fetch_likes_for_art(gid) if a.get("LikeCnt") else []
    comments = c.fetch_comments_for_art(gid) if a.get("CommentCnt") else []
    missing = []
    files = {}
    if retry(c.download_file, a["FileId"], str(d / f"{gid}.dat")):
        files["artwork"] = f"{gid}.dat"
    else:
        missing.append("artwork")
    if a.get("LayerFileId"):
        if retry(c.download_file, a["LayerFileId"], str(d / f"{gid}_layer.dat")):
            files["layer"] = f"{gid}_layer.dat"
        else:
            missing.append("layer")
    if a.get("MusicFileId"):
        p = retry(c.download_music, a, str(d))
        if p:
            files["music"] = Path(p).name
        else:
            missing.append("music")
    meta = {"gallery": a, "likes": likes, "comments": comments, "files": files, "missing": missing,
            "collected_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "complete": True}
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"    likes={len(likes)}/{a.get('LikeCnt')} comments={len(comments)}/{a.get('CommentCnt')} files={list(files)}", flush=True)
print("DONE", flush=True)
