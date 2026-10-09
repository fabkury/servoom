# B. Engineering

## Repositories

| Repository | Visibility | Holds |
|------------|------------|-------|
| `servoom-stats` | public | workflows, collector and aggregator code, `data/` (aggregates as JSON, avatars) |
| `servoom-raw` | private | raw observations (Parquet), current-state table, polling accounts, health state |
| `servoom` | public | the API client (see "Depending on servoom") |

The private repository runs no workflows, so it uses none of the private-repository
Actions minutes. The public repository's jobs reach it with a deploy key
(see `03-secrets.md`).

Raw data cannot go in Actions caches or artifacts of the public repository: both are
readable by people outside the project (artifacts by any signed-in user, caches by
workflows of fork pull requests).

## Depending on servoom

`servoom/python` has no `pyproject.toml` today, so it cannot be installed with pip from
git. Two ways to close that, in order of preference:

1. Add a minimal `pyproject.toml` to `python/` and tag releases. The pipeline then
   installs `git+https://github.com/fabkury/servoom@<tag>#subdirectory=python`.
2. Until then, the workflow checks out servoom at a pinned commit into a subfolder and
   puts `python/` on `PYTHONPATH`.

The collector needs only `DivoomClient`, the HTTP session and, for avatars,
`PixelBeanDecoder`.

## Facts about the API the collector relies on

All from `CLOUD_API.md` and the October 2026 studies:

* `GetCategoryFileListV2` with **one** `FileSize` bit is newest-first. With several bits
  it is not. So the collector pages each (category, size) pair separately: 17 active
  categories by 5 sizes, plus Planet and round, about 90 lists.
* Always send `Version 19`.
* Anonymous callers get at most 1,230 items per list. Anything deeper needs a token.
* `Cloud/GetLikeUserList` is newest-first, 100 per page, so the first *n* entries are the
  *n* most recent likes.
* Each artwork record carries `LikeUTC` and `CommentUTC` (time of last like and comment).
* `GalleryId` and `UserId` are issued in increasing order. New artworks get odd ids two
  apart, though about 14% of even ids are used too. Account ids are odd for
  international sign-ups and even for China-region ones.
* `Cloud/GalleryInfo` answers for any existing artwork id, including uploads held for
  review, and `ReturnCode 1` past the newest one. It needs a token.
* A token was still valid 9.7 hours after login (2026-10-04); the limit is unknown.
* A second login for an account invalidates the first session's token.
* The server answered about 12 requests per second from 4 threads without throttling.
  The collector will use far less.

## Jobs

### Pulse, every hour

Purpose: hourly counters for every upload of the past 30 days, first-seen times for new
uploads, promotion times.

| Step | Requests |
|------|---------:|
| Page every (category, size) list back to 30 days (about 9,000 artworks) | about 390 |
| First page of Recommend and NEW per size | 12 |
| For artworks in the window whose `LikeCnt` rose since the last pulse: first page of the like list | about 60 |
| Id walk: `Cloud/GalleryInfo` on each new artwork id (`06-enhancements.md`, item 6) | about 50 |
| First 3 pages of the Popular sort for the main lists (item 7) | about 40 |
| **Total** | **about 545** |

At 4 requests per second this is about 2 minutes. The pulse works without a token if
needed, except for the like lists (degraded mode, see `03-secrets.md`); anonymously each
list stops at 1,230 items, which shortens the window for the largest lists.

### Refresh, every 4 hours

Runs as the last step of every fourth pulse. It re-aggregates, commits `data/` and calls
the deploy hook (`05-servoom-umbrella.md`). Its own polling:

| Step | Requests |
|------|---------:|
| Id frontiers: highest `UserId` and `GalleryId` | about 50 |
| Comment lists for window artworks whose `CommentUTC` moved since the last refresh | about 40 |
| Sample of 200 newly issued account ids (country and region) | 200 |
| Category totals, contest, tags | about 150 |
| **Total** | **about 440** |

### Snapshot, every day

Purpose: everything else. Decided 2026-10-04: **nothing on the site is slower than
daily**, so the snapshot reads the whole catalog every day, and the request volume is
allowed to be higher than first planned.

| Step | Requests |
|------|---------:|
| Page every (category, size) list to the end: the whole public catalog, about 1.54 million artworks | about 52,000 |
| Like lists (first page) for every artwork whose `LikeUTC` is within 24 hours | about 10,000 |
| Comment lists for artworks whose `CommentUTC` is within 24 hours | about 250 |
| Profiles (`GetSomeoneInfoV2`, `LookScore`) of top artists, about 700 accounts, and `GetExpertListV4` | about 1,500 |
| Id frontiers: binary search for the highest `UserId` and highest `GalleryId` | about 50 |
| Sample of 200 ids issued since yesterday (country and region of new accounts) | 200 |
| Category totals, contest, tags, forum posts | about 150 |
| Profiles of a fixed sample of 200 automated accounts | 200 |
| Avatars of top artists whose `HeadId` changed (file download, decode, lossless WebP) | a few |
| New uploads' files: download, decode, features and hashes (item 5) | about 350 |
| Follow-ups on unlisted and vanished artworks (item 6) | about 450 |
| Divoom's calendar: app version, contest, themes, albums, forum (item 8) | about 10 |
| Deeper like-list paging where more than 100 likes arrived (item 1) | up to 300 |
| **Total** | **about 66,200** |

At 8 requests per second from 4 threads this is about 2.3 hours of polling, plus about
5 minutes to decode and hash the day's files. The server
answered 12 per second without trouble during the October studies.

The job writes a checkpoint to the private repository every 20 minutes, so a run that
fails or is cancelled resumes from the last finished list instead of starting over. The
first list alone (Default, 16x16) takes over an hour.

Also run daily, without extra requests worth counting:

* The automated-account detection described below.
* Canary: one listing with `Version 19` against `Version 99`. A difference means the app
  has a new client level and the collector must be updated.

### Backfill, once, started by hand

The first snapshot is the backfill, since every snapshot now reads the whole catalog.
A manual trigger exists to rerun one after a long outage.

## Politeness

* At most 8 requests per second for the snapshot and 4 for the pulse, from one account
  per job. The snapshot starts at an hour when uploads are lowest.
* Exponential backoff on errors, capped at one minute between attempts. A job gives up
  only after 15 minutes without a single good answer (`API_OUTAGE_SECONDS`); the earlier
  limit of 40 consecutive failures ended a three-hour crawl on a one-minute server hiccup.
* Read-only commands only. The collector never calls `AddWatch`, `GalleryLikeV2` or any
  other write command, so it adds nothing to the counters it measures.
* Hourly cron minutes are offset from :00.

## Storage

### Private repository (raw)

```
obs/artworks/YYYY/MM/DD/pulse-HH.parquet     rows read by a pulse
obs/artworks/YYYY/MM/DD/snapshot.parquet     rows whose values changed, from the snapshot
obs/likes/YYYY/MM/DD.parquet                 (gallery_id, position, user_id, observed_at)
obs/comments/YYYY/MM/DD.parquet              comment id, author id, time, robot flag; no text
obs/profiles/YYYY/MM/DD.parquet              daily profile reads
obs/frontier.csv                             date, max UserId, max GalleryId, ids-in-use share
state/accounts.json                          polling accounts (03-secrets.md)
state/health.json                            failure counters, circuit breaker
```

Rules that keep the repository small:

* Files are append-only and never rewritten, so git stores each once.
* The snapshot writes only artworks that are new or whose counters or flags changed.
  With the whole catalog read daily that is roughly 50,000 rows a day, mostly view
  counters.
* Counter rows keep numbers and flags. Tags, mentions and remix links go to a separate
  table written once per artwork; titles and captions are reduced to a language code
  and a length. Further tables (like events, file features, all uploads, Popular ranks,
  calendar) are listed in `06-enhancements.md`.
* Parquet with zstd compression. Expected growth is about 3 to 5 MB per day, around
  1.5 GB per year with the tables of `06-enhancements.md`. Once a year, old months can be merged into a few files and moved to a release
  asset of the private repository.

The **current-state table** (latest known row for every artwork, about 1.5 million rows,
15 to 25 MB) changes daily, so it must not accumulate in history. It lives on a separate
branch `state` that always has exactly one commit and is force-pushed. If it is ever
lost it can be rebuilt by replaying `obs/`.

### Public repository (aggregates)

```
data/daily.json            one row per day: uploads, likes (people, raw), views, comments, sign-ups
data/hourly/YYYY-MM.json   the same per hour, one file per month
data/cohorts.json          attention curves by upload cohort
data/sizes.json, curation.json, countries.json, retention.json, tags.json, ...
data/artists/index.json    top artists
data/artists/<id>.json     one file per top artist
data/artists/<id>.webp     the artist's avatar, lossless WebP
data/status.json           last run times, gaps, excluded automated ranges
```

Only aggregate tables and top-artist rows. Small text files, committed once a day, so
the git history doubles as a public record of every published number.

## Aggregation

Python with DuckDB over the Parquet files. Every flow is computed as a difference
between two observations of the same artwork divided by the actual time between them,
never by assuming runs are exactly an hour or a day apart, because scheduled workflows
start late or get skipped.

How the main figures are derived:

| Figure | Derivation |
|--------|------------|
| Likes and views per hour, young artworks | pulse-to-pulse counter differences |
| Likes per day, whole catalog | snapshot-to-snapshot differences for every artwork |
| Likes from people | for each artwork with new likes, the first *n* like-list entries are the new likes; count those outside the automated ranges. Where the list was not read, apply the measured share for artworks of the same age band and tier |
| Promotion time | first pulse in which the artwork is in Recommend or has `IsAddRecommend 1` |
| Disappearance | an artwork absent from two consecutive snapshots |
| Sign-ups per day | advance of the highest `UserId` times the share of sampled new ids that exist |
| Distinct likers | distinct account ids in the like event log (`06-enhancements.md`, item 1) |

### Automated-account detection

The excluded set starts as the known block. Each day the aggregator looks at likers
seen in the past 7 days and flags any run of account ids where all of these hold: at
least 200 accounts within a span of 10,000 ids, per-account like counts far more uniform
than the rest, and no uploads newer than the accounts' neighbours. A flagged range is
not excluded automatically. The job opens an issue with the evidence, and the range is
added to a small config file by hand. The methods page lists the ranges and the dates
they were added.

## Site

How the pages are hosted and where they live is specified in `05-servoom-umbrella.md`
(pages in `servoom` under `docs/public/stats/`, data pulled at build). In short:

* A handful of HTML pages written by hand (one per section of `01-content.md`), filled
  from templates for the per-artist pages.
* Each page loads the JSON it needs and draws charts in the browser with one charting
  library, vendored into the repository so the site has no external dependency.
  Observable Plot is the suggestion: it covers lines, bars and heatmaps with little code.
* Light and dark themes, readable on a phone, a table view behind every chart.
* Served from **servoom.pages.dev/stats/**. The snapshot job commits `data/` to
  `servoom-stats` and calls a Cloudflare deploy hook; the site build downloads the data.
  One hook-triggered build a day is far inside the free tier's 500 builds per month.
* `data/*.json` is served with the site, so others can reuse the aggregates.
* Pulse commits go only to the private repository, so they do not trigger deploys.

GitHub Pages remains a drop-in fallback for the same folder.

## Failure handling

* Each job writes its observations before aggregating, and pushes raw data before
  building the site, so a failed build never loses a poll.
* Pushes to the private repository retry with `git pull --rebase`; pulse and snapshot
  write different files and cannot conflict.
* A missed pulse leaves a gap that the next pulse closes with a longer interval. The
  status box on the site shows gaps longer than 3 hours.
* A failed snapshot keeps yesterday's site online.

## Order of work

1. Collector for the pulse, writing to the private repository. Let it run for a week.
2. Snapshot and current-state table; backfill.
3. Aggregation for the Pulse page and the status box; first public deploy.
4. Remaining pages, one at a time, as enough history accumulates.
