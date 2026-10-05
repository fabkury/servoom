# One site, two pillars: fitting the statistics under servoom

Decided on 2026-10-04: everything lives under the servoom name, and the only public site
is **servoom.pages.dev**, refactored to carry two pillars:

* **Download**: the existing tool for downloading one's own artworks.
* **Statistics**: the community statistics described in the other documents here.

Where this document and `02-engineering.md` disagree about hosting or repositories, this
one wins.

## Repositories

| Repository | Visibility | Status | Holds |
|------------|------------|--------|-------|
| `servoom` | public | exists | the library (`python/`, `c/`), the whole website (`docs/`), these design documents |
| `servoom-stats` | public | new | the pipeline (collector, aggregator, workflows) and its output: `data/` with aggregate JSON and top-artist avatars |
| `servoom-raw` | private | new | raw observations, the current-state branch, `state/accounts.json`, `state/health.json` |
| `servoom-private` | private | exists | APK research; unrelated and left alone, which is why the raw repository needs another name |

Site code and data are kept apart on purpose: `servoom` changes when a person edits
pages, `servoom-stats` changes every day by machine.

## How data reaches the site

```
servoom-stats (Actions, 4-hourly)               servoom (Cloudflare Pages build)
  snapshot job                                   on push to main, or on deploy hook
    aggregate ──► commit data/ ──► POST hook ──►   prebuild: download servoom-stats data/
                                                   into docs/public/stats/data/
                                                   vite build ──► servoom.pages.dev
```

* The build stays in Cloudflare, with its git integration, as today.
* A new prebuild script, `docs/scripts/fetch-stats.mjs`, downloads the `data/` folder of
  `servoom-stats` (a public tarball, no credentials) into `docs/public/stats/data/`,
  which is git-ignored. Vite copies `public/` into the build, so the data is served from
  the same origin as the pages.
* The refresh job in `servoom-stats` (every 4 hours, see "Update cadence") ends by calling a **Cloudflare deploy hook**. The hook
  URL is the only new secret (`CF_DEPLOY_HOOK_URL` in `servoom-stats`); all it can do is
  start a rebuild.
* If the download fails, the build fails and the previous deploy stays online. Old data
  does not fail a build: the status box on the site reports its age.
* The pipeline cannot see whether the deploy worked, so each snapshot run first reads
  `servoom.pages.dev/stats/data/status.json` and opens an issue if the live data is more
  than 12 hours old.
* Builds per month: about 180 from the hook plus pushes, against a free limit of 500.
* The GitHub Pages mirror (`deploy-pages.yml`) runs the same `npm run build`, so it
  picks up the data the same way, on pushes only.

Data format changes must be additive, because pages (in `servoom`) and data (in
`servoom-stats`) deploy on different schedules. `data/status.json` carries a schema
number the pages check.

## Site layout

| URL | Content | Built from |
|-----|---------|------------|
| `/` | new landing page with two cards, Download and Statistics | `docs/index.html`, plain HTML |
| `/download/` | the existing React tool, moved from `/` | `docs/download/index.html` as a second Vite entry, with `docs/src/` unchanged |
| `/stats/` and `/stats/<page>.html` | statistics pages | `docs/public/stats/`, hand-written HTML, a vendored chart library, shared CSS |
| `/stats/artist.html#<id>` | one template page for every top artist | same; it loads `data/artists/<id>.json` |
| `/stats/data/…` | aggregate JSON and avatars | downloaded at build |

Details:

* The pipeline produces only JSON and WebP. It no longer writes HTML; per-artist pages
  are one static template driven by the URL fragment.
* The strict isolation headers in `docs/public/_headers` (needed by Pyodide) move from
  `/*` to `/download/*`, so the landing and statistics pages are ordinary pages.
* Statistics pages use relative URLs only, so they also work under the `/servoom/` base
  path of the GitHub Pages mirror.
* The tool has no deep links today, so moving it needs no redirects beyond the landing
  page's card. Old bookmarks of `/` land on the landing page.
* A small shared header (Download, Statistics, GitHub) and stylesheet are used by all
  three parts.

## What moves or changes, by repository

### `servoom`

| Change | Where |
|--------|-------|
| Add `pyproject.toml` and tag releases, so the pipeline can pip-install the client | `python/` |
| New landing page | `docs/index.html` |
| Tool entry moves to `/download/`; Vite gets two inputs | `docs/download/index.html`, `docs/vite.config.ts` |
| Statistics pages, chart library, shared CSS | `docs/public/stats/` |
| Data fetch at build; ignore the fetched folder | `docs/scripts/fetch-stats.mjs`, `docs/package.json` (`prebuild`, `predev`), `.gitignore` |
| Scope isolation headers to the tool | `docs/public/_headers` |
| Download tool reads `stats/data/benchmarks.json` and shows percentiles for the user's own artworks | `docs/src/` |
| README: describe both pillars | `README.md`, `docs/README.md` |

Nothing moves out of `servoom`. These design documents can stay here or move to
`servoom-stats` once it exists.

### `servoom-stats` (new)

```
collector/        pulse and snapshot polling (uses the servoom client)
aggregate/        DuckDB queries, writes data/
data/             aggregates and avatars, committed daily
config/           automated ranges, artist exclusion list
.github/workflows pulse.yml, snapshot.yml, backfill.yml
```

Secrets: `RAW_REPO_DEPLOY_KEY`, `CF_DEPLOY_HOOK_URL`. Variable:
`ACCOUNT_EMAIL_DOMAIN=servoom.invalid`.

### `servoom-raw` (new, private)

As in `02-engineering.md`, "Private repository (raw)". No workflows.

### Cloudflare

One new setting on the existing project: create a deploy hook for the production branch.
The build command and output folder stay as they are.

## Generated account addresses

`<random>@servoom.invalid`. `.invalid` is a reserved top-level domain that can never be
registered, so no real mailbox can be hit. The accounts cannot receive mail, which is
fine: they are disposable and recovery is by replacement. `/UserRegister` accepted this form in a test on 2026-10-04; the
account created then is the first pool account.

## Still open

Nothing blocks implementation. Two things will only be learned by running:

1. The upper limit of token lifetime (at least 9.7 hours).
2. The right request fields for `GetNewAppVersion`, if app releases are wanted as chart
   markers.

## Update cadence: every 4 hours

Added 2026-10-04. The site refreshes six times a day, not once.

| Job | When | Polls Divoom | Publishes |
|-----|------|--------------|-----------|
| Pulse | hourly | about 545 requests (uploads of the past 30 days, new artwork ids, Popular pages) | nothing; appends raw rows |
| Refresh | every 4 hours, as the last step of that hour's pulse | about 440 more (id frontiers, new comments, new-account sample, category totals) | re-aggregates, commits `data/`, calls the deploy hook |
| Snapshot | daily, replaces one of the six refreshes | about 66,200 (the whole catalog, new files) | the same, plus everything that needs the deep read |

What is fresh to 4 hours: uploads, likes and views on artworks up to 30 days old, the
hour-of-day rhythm, promotions, comments on those artworks, new sign-ups and their
countries, category and contest totals, and top artists' likes on recent uploads.
What is daily, and nothing is slower: whole-catalog like and view totals, back-catalog
figures, like lists and comments outside the 30-day window, artist profiles (followers,
score), detection of automated accounts. Each figure on the site
shows its own "as of" time.

Budget:

* **Divoom**: about 82,000 requests a day in total (66,200 snapshot, 13,100 pulse, 2,200
  refresh), up from 19,000 in the first plan.
* **Cloudflare**: 6 builds a day is about 180 a month, plus pushes to `servoom`, against
  500 a month on the free plan. The cap is per account, so other projects on the account
  count too. Every 2 hours (about 360) would still fit but leaves little room; hourly
  (about 720) does not.
* **GitHub Actions**: unmetered on a public repository; about 8,400 minutes a month in
  all (`04-actions-budget.md`).
* **Git**: about 2,200 small data commits a year in `servoom-stats`, which is fine for
  JSON of this size. Avatars are committed only when they change.
* The stale-data alarm tightens from 48 hours to 12.
