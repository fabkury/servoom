"""After the main run: does either endpoint react to request parameters?

For each variant, two calls 2 s apart; prints the item names returned and whether the
variant pool overlaps the baseline pool from samples.jsonl. About 20 requests total.
Output goes to probe_params.txt.
"""
import json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "python"))
from credentials import TEST_ACCOUNTS
from servoom.client import DivoomClient
from servoom.http import DivoomSession

# baseline pools from the main run
pools = {"/Cloud/GetHotTag": set(), "/Cloud/GetHotExpert": set()}
for line in open(os.path.join(HERE, "samples.jsonl"), encoding="utf-8"):
    r = json.loads(line)
    resp = r.get("resp") or {}
    if "TagList" in resp:
        pools[r["ep"]].update(t["TagName"] for t in resp["TagList"])
    if "ExpertList" in resp:
        pools[r["ep"]].update(e["NickName"] for e in resp["ExpertList"])

acct = TEST_ACCOUNTS["test_01"]
client = DivoomClient(email=acct["email"], md5_password=acct["md5"])
assert client.login()
auth = client._auth()
post = client._session.post_json
anon = DivoomSession().post_json

def names(resp):
    if "TagList" in resp:
        return [t["TagName"] or "(empty)" for t in resp["TagList"]]
    if "ExpertList" in resp:
        return [e["NickName"] for e in resp["ExpertList"]]
    return None

variants = [
    ("no token", None, {}),
    ("RegionId 86 (China)", auth, {"RegionId": 86}),
    ("RegionId 1", auth, {"RegionId": 1}),
    ("Language zh", auth, {"Language": "zh", "CountryISOCode": "CN"}),
    ("StartNum 1 EndNum 20", auth, {"StartNum": 1, "EndNum": 20}),
    ("Num 20 / TagNum 20 / ExpertNum 20", auth, {"Num": 20, "TagNum": 20, "ExpertNum": 20, "Count": 20}),
    ("FileSize 1 (16px)", auth, {"FileSize": 1}),
    ("Classify 18", auth, {"Classify": 18}),
]
lines = []
for ep in pools:
    lines.append(f"===== {ep}  (baseline pool: {len(pools[ep])} items)")
    for label, a, extra in variants:
        got = []
        for _ in range(2):
            payload = {**(a or {}), **extra}
            resp = (post if a else anon)(ep, payload)
            n = names(resp)
            got.append(n)
            time.sleep(2)
        rc = resp.get("ReturnCode")
        flat = [x for g in got if g for x in g]
        novel = sorted(set(flat) - pools[ep] - {"(empty)"}) if flat else []
        sizes = [len(g) if g else None for g in got]
        lines.append(f"- {label}: rc={rc} sizes={sizes} same_two_calls={got[0] == got[1]} "
                     f"items_outside_baseline={novel} first={got[0]}")
    lines.append("")
text = "\n".join(lines)
open(os.path.join(HERE, "probe_params.txt"), "w", encoding="utf-8").write(text + "\n")
sys.stdout.reconfigure(encoding="utf-8")
print(text)
