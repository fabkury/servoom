"""Confirm candidate UserIds (from the local like-count fingerprint) with GetSomeoneInfoV2,
using the fresh bots_check_01 account. Read-only."""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))
from servoom.client import DivoomClient
from credentials import TEST_ACCOUNTS

a = TEST_ACCOUNTS["bots_check_01"]
c = DivoomClient(email=a["email"], md5_password=a["md5"])
assert c.login()
out = {}
for uid in [int(x) for x in sys.argv[1:]]:
    r = c.fetch_someone_info(uid) or {}
    out[uid] = r
    print(uid, {k: r.get(k) for k in ("UserName", "Level", "FansCnt", "FollowCnt", "LikeCnt", "Score", "UserSign", "RegionId", "CountryISOCode") if k in r})
    time.sleep(0.3)
Path(__file__).with_name("out").joinpath("candidates_info.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
