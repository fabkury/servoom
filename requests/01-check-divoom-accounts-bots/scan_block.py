"""Fetch GetSomeoneInfoV2 for every id in a range (default: the known like-block,
even ids 400971852..400975850) with the fresh bots_check_01 account. Read-only.
Writes out/block_profiles.jsonl incrementally and prints name matches."""
import json, sys, time, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))
from servoom.client import DivoomClient
from credentials import TEST_ACCOUNTS

lo, hi, step = (int(x) for x in (sys.argv[1:4] or (400971852, 400975850, 2)))
WANT = {"drew", "julycat"}
a = TEST_ACCOUNTS["bots_check_01"]
c = DivoomClient(email=a["email"], md5_password=a["md5"])
assert c.login()
out = Path(__file__).with_name("out") / "block_profiles.jsonl"
done = set()
if out.exists():
    for line in out.open(encoding="utf-8"):
        done.add(json.loads(line)["uid"])
ids = [u for u in range(lo, hi + 1, step) if u not in done]
lock = threading.Lock(); fh = out.open("a", encoding="utf-8")
KEEP = ("NickName", "Level", "FansCnt", "FollowCnt", "LikeCnt", "Score", "CountryISOCode", "RegionId", "HeadId", "PixelFlag", "MedalList")
def one(uid):
    for _ in range(3):
        try:
            r = c.fetch_someone_info(uid)
            break
        except Exception:
            time.sleep(2); r = None
    row = {"uid": uid, **({k: r.get(k) for k in KEEP} if r else {"missing": True})}
    with lock:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n"); fh.flush()
        if (row.get("NickName") or "").strip().lower() in WANT:
            print("MATCH", row, flush=True)
    time.sleep(0.6)
with ThreadPoolExecutor(4) as ex:
    list(ex.map(one, ids))
print("done", len(ids))
