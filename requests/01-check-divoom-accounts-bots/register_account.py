"""Register one fresh throwaway Divoom account and append it to the git-ignored
python/credentials.py TEST_ACCOUNTS (key bots_check_01). Never prints the secrets."""
import hashlib, json, secrets, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "python"))
from servoom.http import DivoomSession

KEY = "bots_check_01"
creds_path = Path(__file__).resolve().parents[2] / "python" / "credentials.py"
if KEY in creds_path.read_text(encoding="utf-8"):
    sys.exit(f"{KEY} already present in credentials.py")

pw = secrets.token_urlsafe(18)
email = f"check-{secrets.token_hex(5)}@servoom.invalid"
md5 = hashlib.md5(pw.encode()).hexdigest()
s = DivoomSession()
r = s.post_json("/UserRegister", {"Email": email, "Password": md5, "CountryISOCode": "US",
                                  "Language": "en", "TimeZone": "America/New_York"})
print("register:", {k: v for k, v in r.items() if k not in ("Token",)})
if r.get("ReturnCode") != 0:
    sys.exit("registration refused")
login = s.post_json("/UserLogin", {"Email": email, "Password": md5})
print("login ReturnCode:", login.get("ReturnCode"), "UserId:", login.get("UserId"))
uid = login["UserId"]
acct = {"email": email, "password": pw, "md5": md5, "user_id": uid,
        "created": time.strftime("%Y-%m-%d")}
with creds_path.open("a", encoding="utf-8") as f:
    f.write(f"\n# Fresh read-only account for requests/01-check-divoom-accounts-bots (2026-10-09).\n"
            f"TEST_ACCOUNTS[{KEY!r}] = {acct!r}\n")
Path(__file__).with_name("out").joinpath("account.json").write_text(
    json.dumps({"key": KEY, "user_id": uid, "created": acct["created"],
                "where": "python/credentials.py TEST_ACCOUNTS (git-ignored)"}, indent=2))
print("stored as TEST_ACCOUNTS[%r], user_id %s" % (KEY, uid))
