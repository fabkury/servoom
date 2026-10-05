# C. Secrets and self-healing logins

## What is secret

| Item | Sensitivity | Where it lives |
|------|-------------|----------------|
| Deploy key for the private repository (SSH, read and write) | the only real secret | GitHub Actions secret `RAW_REPO_DEPLOY_KEY` in `servoom-stats` |
| Cloudflare deploy hook URL | low: it can only trigger a rebuild of the site | GitHub Actions secret `CF_DEPLOY_HOOK_URL` in `servoom-stats` |
| Polling accounts: email, password, MD5, user id, last token | low: throwaway accounts with no data of value | `state/accounts.json` in the private repository |
| Raw observations | personal-ish (user ids of uploaders and likers) | private repository |

The Divoom credentials are deliberately **not** GitHub secrets. A workflow cannot update
a GitHub secret with its built-in token; doing so needs a personal access token with
permission to write secrets, which is a stronger and expiring credential than anything it
would protect. Keeping the accounts in a file in the private repository lets the pipeline
rewrite them freely with the access it already has, and a deploy key does not expire.

If the deploy key leaked, the damage is the raw data and a few throwaway accounts. The
fix is to replace the key and let the pipeline register new accounts.

## The account pool

`state/accounts.json`:

```json
{
  "accounts": [
    {"email": "...", "password": "...", "md5": "...", "user_id": 0,
     "role": "pulse", "status": "ok", "created": "2026-10-10",
     "token": "...", "token_at": "...", "strikes": 0, "last_ok": "..."}
  ],
  "last_registration": "2026-10-10"
}
```

* Three accounts to start: one with role `pulse`, one with role `snapshot`, one `spare`.
* **One account per job.** A login invalidates the account's other sessions, so the
  hourly and daily jobs must never share an account. Each workflow also has a
  `concurrency` group so two runs of the same job cannot overlap.
* The token is stored and reused. A job logs in only when the stored token is rejected
  (`ReturnCode 11`). That keeps logins rare: a token was still good 7.9 hours after
  login in a test on 2026-10-04.
* The accounts are new, dedicated ones. The existing test accounts and the personal
  account are not used.

## Health checks

Every job starts with a canary before polling:

1. A listing request deeper than item 1,230 in a large category. An empty page means the
   token is not being honoured (the anonymous cap), even though the server answers
   `ReturnCode 0`.
2. One `Cloud/GetLikeUserList` call on a known artwork.

Failures are classified before anything is blamed on the account:

| Symptom | Meaning | Action |
|---------|---------|--------|
| Network error, HTTP 5xx, timeouts | Divoom or the runner is having trouble | retry with backoff, then end the run; no strike |
| `ReturnCode 11` with a stored token | token expired or replaced | log in again; no strike if that works |
| Login refused | wrong password, or account disabled | strike |
| Login accepted but the canary fails | account restricted | strike |
| Canary passes, later requests fail in bulk | throttling | slow down, end the run, no strike |

## Self-healing

```
account ok ──strike──► 1 strike ──strike──► 2 strikes ──strike──► status "bad"
                                                                      │
                                   promote the spare to this role ◄───┘
                                                │
                              no spare left?    ▼
                    register a new account (at most one per 7 days)
                                                │
                         open a GitHub issue describing what happened
```

* **Rotation.** After three strikes in a row the account is marked `bad` and the spare
  takes its role in the same run.
* **Registration.** When the pool has no spare, the job calls `/UserRegister` (no email
  verification is needed) with a generated address and a random 24-character password,
  and adds the account to the file. `last_registration` enforces the cap of one new
  account per 7 days.
* **Addresses.** `<random>@servoom.invalid`, set in the repository variable
  `ACCOUNT_EMAIL_DOMAIN`. `.invalid` is a reserved top-level domain that nobody can
  register, so no real mailbox can be hit. `/UserRegister` accepted it in a test on
  2026-10-04.
* **Circuit breaker.** If a newly registered account also fails, or the cap blocks a
  needed registration, `state/health.json` is set to `halted`. Jobs then exit in a few
  seconds until a person clears the flag. This stops the pipeline from creating accounts
  in a loop if Divoom starts refusing them.
* **Degraded mode.** While halted or without a working account, the pulse still runs
  anonymously: list heads up to 1,230 items need no token, which covers uploads and
  counters for young artworks. Like lists and the deep snapshot wait. The site's status
  box says so.
* **Notification.** Rotation, registration and halting each open or update one GitHub
  issue in the public repository, written with the workflow's own token
  (`issues: write`). The issue text never contains credentials, emails or user ids.

## Keeping secrets out of public view

The public repository's workflow logs are readable by anyone.

* The collector never logs request bodies, tokens, emails or account ids. Tokens and
  passwords read from `accounts.json` are registered with `::add-mask::` as a second
  line of defence.
* The deploy key is exposed only to the steps that clone and push the private
  repository, through a GitHub environment (`polling`) restricted to the default branch.
* Workflows trigger on `schedule` and `workflow_dispatch` only. No `pull_request_target`,
  and pull requests from forks get no secrets.
* Workflow `permissions` default to read-only; the publish step adds `contents: write`,
  the notify step `issues: write`.
* Third-party actions are pinned to commit hashes.
* Aggregates pass a check before commit: no column named like an id, name or email
  outside `data/artists/`, and every id in `data/artists/` is in the top-artist set.

## What a person still has to do

* Create the two repositories, the deploy key and the first three accounts (a one-time
  script can do the accounts).
* Clear the `halted` flag after looking at why it was set.
* Approve additions to the list of automated ranges (`02-engineering.md`).
