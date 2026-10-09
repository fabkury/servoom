# Fresh check account (secrets are NOT here)

- Key: `TEST_ACCOUNTS["bots_check_01"]` in the git-ignored `python/credentials.py`
- UserId 405031725, registered 2026-10-09 via `/UserRegister` (email on the
  disposable `@servoom.invalid` domain, country US, timezone America/New_York)
- Purpose: read-only lookups that must not touch the main account. Reuse it with
  `DivoomClient(email=a["email"], md5_password=a["md5"])`.
- Usage so far: ~2,000 `GetSomeoneInfoV2` + a handful of `GetSomeoneListV3` calls.
