# Divoom community statistics site: design

Design for a public, self-updating website with statistics about the Divoom cloud
gallery community. Nothing here is implemented. The design builds on what the one-off
studies of 2026-10-02 to 2026-10-04 measured (Recommend feed, attention market, like
block) and on [`CLOUD_API.md`](../../CLOUD_API.md).

| Document | Question it answers |
|----------|---------------------|
| [`01-content.md`](01-content.md) | A. What the site shows, and what repeated polling adds over a single crawl |
| [`02-engineering.md`](02-engineering.md) | B. What is polled, how often, where it is stored, how pages are built |
| [`03-secrets.md`](03-secrets.md) | C. Credentials, self-healing logins, what is secret and what is not |
| [`04-actions-budget.md`](04-actions-budget.md) | D. GitHub Actions limits and how the runs fit in them |
| [`06-enhancements.md`](06-enhancements.md) | Twelve additions that use data the first design left unused: like log, sign-up funnel, tags, files, all uploads, Popular ranking, calendar, and more |
| [`05-servoom-umbrella.md`](05-servoom-umbrella.md) | How it all fits under servoom: repositories, one site with two pillars, what moves where. Newest; it wins where the others differ on hosting or repositories. |

## Status

Implemented on 2026-10-05. The pipeline is the public repository
[servoom-stats](https://github.com/fabkury/servoom-stats); raw data is in the private
`servoom-raw`; the pages are in `docs/public/stats/` here. Where the code differs from
these documents, the code is right. Known differences:

* **Checkpointing in the snapshot.** The crawl is saved to branch `state-crawl` of the
  raw repository every 20 minutes (the raw rows of the lists finished so far) and once
  more when it is complete. A run started within six hours of a crawl that never became
  a snapshot resumes from the last finished list, or reuses the finished crawl.
* **State lives on branches** of the raw repository, `state-pulse` and `state-snap`,
  one per job, so the hourly and daily jobs never write the same file.
* **Languages.** Titles and comments are classified by writing system (Latin, Chinese
  characters, kana, Cyrillic, ...), not by language.
* **Layers.** Files record whether a layer file exists, not how many layers it has.
* **Site languages.** The landing and statistics pages are offered in the tool's five
  languages (English, Spanish, Chinese, Japanese, Russian), sharing its language choice.
* **Listings are not a reliable index of recent uploads.** On 2026-10-05 several
  (category, size) lists were missing artworks of whole date ranges (for example Nature
  16x16 had nothing between 4 and 21 days old) although those artworks still existed
  and were public, and the same lists showed hundreds of 2020-era artworks with no
  likes or views right after the newest 60. The day before, the same lists were
  complete and in order. The cause is on Divoom's side and unknown. The pulse therefore
  re-reads known artworks one by one when a listing omits them, reads every list with a
  long look-ahead once a day, and the snapshot never treats a still-public artwork as
  gone. Upload counts for affected days can still read low until the listings recover.
* **Listing counters lag.** Like and view counters in listings refresh in batches,
  roughly every 15 to 30 minutes, so hourly figures can be shifted by that much.
* **Not built:** the monthly workflow re-enable step (daily commits keep the schedules
  alive), and yearly compaction of old raw files.

## Decisions already taken

| Topic | Decision |
|-------|----------|
| People | Aggregates for everyone. Names only for top artists, meaning accounts Divoom itself already features (Recommend feed, expert list, ambassador badge). |
| Automated likes | Corrected "semi-quietly": the headline like figures exclude the like block, the raw counter is shown beside them, and the methods page explains the correction with one chart. No dedicated page about the block. |
| Repositories | `servoom-stats` (new, public) holds the pipeline and the aggregate data. `servoom-raw` (new, private) holds raw data and accounts. The site's pages live in `servoom`. |
| Raw data | Not public. Per-artwork and per-account rows, including the like event log, live in a private companion repository; rows older than 24 months are reduced to aggregates. |
| Cadence | A pulse every hour over the past 30 days of uploads, a site refresh every 4 hours, a whole-catalog snapshot every two days (daily until 2026-10-09). Nothing on the site is slower than two days. |
| Account recovery | One polling account per job plus three spares. A capped or failing account is retired and a spare takes over in the same run; the pool registers at most one new account per 3 days and opens an issue. |
| Site stack | Hand-written static pages under `docs/public/stats/` in `servoom`; the pipeline writes only JSON and avatars. |
| Hosting | The existing servoom.pages.dev, refactored into a landing page, `/download/` (the current tool) and `/stats/`. Cloudflare keeps building from `servoom`; the build pulls the data and a daily deploy hook triggers it. |
| Images | Avatars of top artists only, rehosted as lossless WebP. No artworks. |
| Generated accounts | `<random>@servoom.invalid`, pending one test registration. |
| Terms of use | Proceed as designed (see "Terms of use" below). |

## Architecture in one picture

```
            GitHub Actions (public repo, standard runners)
            ┌───────────────────────────────────────────────┐
  cron ───► │ pulse (hourly)      snapshot (daily)          │
            │   poll Divoom ──►   poll Divoom               │
            │   append raw        append raw, aggregate,    │
            │                     commit data, ping hook    │
            └──────┬──────────────────┬───────────────┬─────┘
                   │ raw rows         │ aggregates    │ site
                   ▼                  ▼               ▼
          servoom-raw           servoom-stats    servoom.pages.dev/stats
          (Parquet, state,      data/*.json      (pages in servoom, data
           accounts.json)       (git history)     pulled at build)
```

## Checked on 2026-10-04

| Assumption | Result |
|------------|--------|
| A login token outlives a single run | A token issued at 14:25 UTC still passed the deep-listing and like-list checks 7.9 hours later with no login in between. The upper limit is unknown, so the collector still handles `ReturnCode 11`. |
| The id frontiers can be read | Yes. `Cloud/GalleryInfo` (token required) answers for ids above the newest listed artwork, including uploads still held for photo review (`CheckConfirm 1`), and `ReturnCode 1` beyond the newest id. `GetSomeoneInfoV2` (no token) does the same for accounts. |
| `GalleryId` step | Current artworks get **odd** ids, two apart; 11 of the 13 newest odd ids held a record. Uploads per day is therefore about half the id advance. The October 4 report's caption that two in three uploads are not public had this backwards and was corrected: about two in three stay public. |
| Anonymous degraded mode | List heads and profiles answer without a token; `Cloud/GalleryInfo` and like lists do not. |
| Public repositories are unmetered | Confirmed in GitHub's billing documentation: standard runners are free for public repositories. Job limit 6 hours. Pages: 1 GB site, 100 GB per month soft bandwidth. |
| 60-day rule for scheduled workflows | Applies to public repositories; new commits reset it. The daily aggregate commit to the public repository satisfies it. The monthly re-enable step stays as a safeguard. |
| Token lifetime, again | The same token still worked 9.7 hours after login. |
| `Cloud/GalleryInfo` on unlisted ids | Of 400 consecutive odd ids about two days old: 308 public, 20 other accounts' **private** uploads (`PrivateFlag 1`, `IsDel 8`), 17 removed ones (`IsDel 1`), 55 with no record. So it does answer for private uploads. About 14% of even ids also exist, so the id walk reads every id, not only odd ones. |
| Calendar sources | `Cloud/GetMatchInfo`, `Discover/GetTheme`, `Discover/GetTopNew`, `Mall/GetListV2`, `GetStoreV2`, `Discover/GetStoreList`, `GetGalleryAdvert` and `Lottery/Announce` answer without a device. `Discount/GetNewDiscount` answers empty. `GetNewAppVersion` answers only `Version 1` with the fields tried, so app releases are not available from it yet. |
| Registration at `servoom.invalid` | Accepted. One account was registered on 2026-10-04, logged in, paged past the anonymous cap and read a like list. It is kept as the first pool account (`stats_pool_01` in the git-ignored `python/credentials.py`). |
| Leaving Cloudflare's build later | A git-connected Pages project cannot be converted to Direct Upload, but automatic deployments can be switched off and `wrangler pages deploy` used on the same project. The choice to build in Cloudflare is therefore reversible. |
| File downloads | About 350 a day is well within what the owner has downloaded in a day before. |
| `pip install` of servoom from git | **Does not work today**: `python/` has no `pyproject.toml` and the repository has no tags. See `02-engineering.md`, "Depending on servoom". |

## Terms of use

Two documents were found, neither of which names the server API:

* The **Divoom App User Agreement** (`m.divoom-gz.com/DivoomUserAgreement.html`, about
  600 words, undated) covers "using our application" without defining it. It says: "You
  may not use any automated means, such as robots or spiders, to access our application",
  and reserves the right to terminate access.
* The **store terms** at `divoom.com/policies/terms-of-service` govern the online shop
  only.

No agreement or documentation for the cloud API was found, and no permission process.
The owner's reading is that the app agreement governs the app, not direct calls to the
servers, and the decision is to proceed as designed. The opposite reading is also
plausible: the accounts are app accounts and the servers are the app's backend, so Divoom
may treat the clause as covering this. The practical consequences are closed polling
accounts or blocked requests, which the design already tolerates, and a request to stop,
which would be honoured. The site carries a contact address and says it is unofficial.

## Still open

See the list at the end of `05-servoom-umbrella.md`.
