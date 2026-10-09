# Questions and answers (intake, 2026-10-09)

**Q1. How should I locate the two accounts' UserIds?** (screenshots show only the
display names Drew and julycat; /SearchUser is broken server-side)
**A:** Any means that works: servoom-raw snapshot rows (UserName -> UserId), then scan
category feeds for the visible artworks and confirm with GetSomeoneInfoV2.

**Q2. Why are they suspected bots and what would convince you?**
**A:** They liked/followed me suspiciously. Check membership in the known like-block
(sequential ids 400971852-400975850), like/follow cadence, and whether uploads are copies.

**Q3. Where should the new account be stored for reuse?**
**A:** python/credentials.py TEST_ACCOUNTS (git-ignored), plus a redacted note in the
request folder.

**Q4. Email form for the new account?**
**A:** something@servoom.invalid (the disposable scheme the stats pipeline uses).

**Q5. May the check read the main account's own data (notifications, like lists)?**
**A:** No, fresh account only.

**Q6. Should the fresh account stay read-only toward the two suspects?**
**A:** Read-only: no follows, likes, comments or messages.
