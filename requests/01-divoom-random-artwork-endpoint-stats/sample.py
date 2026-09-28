"""Sample Divoom's two call-to-call-varying endpoints at a fixed pace.

Alternates POST /Cloud/GetHotTag and POST /Cloud/GetHotExpert, one request per second,
for DURATION seconds, logged in as the throwaway test account. Every raw response is
appended to samples.jsonl as one JSON line: {"i", "t" (unix), "ep", "ms", "resp"} or
{"i", "t", "ep", "error"}. Progress goes to sample.log.

Run from the repository root:  python requests/01-.../sample.py
"""
import json, os, sys, time, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "python"))
from credentials import TEST_ACCOUNTS          # git-ignored
from servoom.client import DivoomClient

DURATION = 30 * 60          # seconds of querying
PERIOD = 1.0                # seconds between request starts
ENDPOINTS = ["/Cloud/GetHotTag", "/Cloud/GetHotExpert"]
OUT = os.path.join(HERE, "samples.jsonl")
LOG = os.path.join(HERE, "sample.log")

def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

acct = TEST_ACCOUNTS["test_01"]
client = DivoomClient(email=acct["email"], md5_password=acct["md5"])
if not client.login():
    log("login failed"); sys.exit(1)
auth = client._auth()
post = client._session.post_json
log(f"start: {DURATION}s at {PERIOD}s period, alternating {ENDPOINTS}")

t0 = time.time()
i = 0
errors = 0
with open(OUT, "a", encoding="utf-8") as out:
    while time.time() - t0 < DURATION:
        ep = ENDPOINTS[i % len(ENDPOINTS)]
        due = t0 + i * PERIOD
        now = time.time()
        if due > now:
            time.sleep(due - now)
        start = time.time()
        rec = {"i": i, "t": round(start, 3), "ep": ep}
        try:
            resp = post(ep, dict(auth))
            rec["ms"] = round((time.time() - start) * 1000)
            rec["resp"] = resp
        except Exception as exc:
            errors += 1
            rec["error"] = repr(exc)
            log(f"#{i} {ep} error: {exc!r}")
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.flush()
        i += 1
        if i % 100 == 0:
            log(f"{i} requests, {errors} errors, {time.time()-t0:.0f}s elapsed")
log(f"done: {i} requests, {errors} errors, {time.time()-t0:.0f}s")
