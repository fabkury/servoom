# D. GitHub Actions budget

## The premise

**Public repositories do not have a monthly minute allowance.** Standard GitHub-hosted
runners are free and unmetered for public repositories. The 2,000 free minutes per month
apply to private repositories on the Free plan. Since the workflows live in the public
repository and the private one runs none, minutes are not the constraint.

The unmetered status, the 6-hour job limit, the Pages limits and the 60-day rule were
re-checked against GitHub's documentation on 2026-10-04. The other rows are from memory.

## The limits that do apply

| Limit | Value | Effect on this design |
|-------|-------|-----------------------|
| Job run time | 6 hours | the daily snapshot takes about 3.5 hours and checkpoints every 20 minutes, so a cancelled run resumes |
| Concurrent jobs (Free plan) | 20 | at most two run at once (pulse and snapshot) |
| Shortest cron interval | 5 minutes | not needed; hourly is used |
| Schedule accuracy | runs start late under load, often 5 to 30 minutes, and can be dropped | flows use the real time between observations; cron minutes avoid :00 |
| Scheduled workflows disabled after 60 days without repository activity | public repositories; new commits reset the clock | the daily aggregate commit resets it; a monthly step also re-enables the workflows through the API as a safeguard |
| Cloudflare Pages builds (chosen host) | 500 per month on the free tier | one deploy a day |
| GitHub Pages (fallback host) | 1 GB site, 100 GB per month soft bandwidth | aggregates and pages are a few MB |
| Repository size | keep under 1 GB, files under 100 MB | see storage rules in `02-engineering.md` |
| Actions cache | 10 GB per repository, entries dropped after 7 days unused | used only for the pip cache |

## What the runs cost

| Job | Runs per month | Minutes per run | Minutes per month |
|-----|---------------:|----------------:|------------------:|
| Pulse (about 545 requests, plus setup and push) | 720 | 4 | 2,880 |
| Refresh (about 440 requests, re-aggregate, commit, deploy hook; added to every fourth pulse) | 150 | +4 | 600 |
| Snapshot (about 66,200 requests, file decoding, aggregation, commit, deploy hook) | 30 | 165 | 4,950 |
| **Total** | | | **about 8,400** |

Per-run overhead is about one minute: checkout, Python from the runner image, cached pip
install, a shallow clone of the private repository's `state` branch and the current
month of `obs/`.

## Spending them wisely anyway

Free does not mean unlimited goodwill, from GitHub or from Divoom. The design keeps runs
short for three reasons: short jobs fail less, they are less likely to be delayed, and
the real scarce resource is requests to Divoom's servers.

* **One job per run**, no matrix. Minutes are rounded up per
  job, so many small jobs waste more than one longer one.
* **The pulse reads only what moves fast**: 30 days of uploads. The daily snapshot reads
  the whole catalog, by decision, so that no figure on the site is older than a day.
* **Like lists only where a counter moved.**
* **Exit early.** If the health flag is `halted`, or Divoom is unreachable, the job ends
  in seconds.
* **`timeout-minutes`** on every job: 15 for the pulse, 300 for the snapshot.
* **`concurrency`** per workflow, without cancelling a running job, so a late run never
  overlaps the next.
* **Shallow, sparse clones** of the private repository; jobs append files and never need
  its history.

## If the workflows ever had to be private

Should the pipeline move to a private repository, the 2,000-minute allowance would apply
and the plan above would not fit. The daily whole-catalog read alone would exceed it, so
the site would have to fall back to weekly back-catalog figures. This variant fits:

| Job | Runs per month | Minutes per run | Minutes per month |
|-----|---------------:|----------------:|------------------:|
| Pulse every 3 hours | 240 | 3 | 720 |
| Snapshot daily, back catalog read over 14 days in place of 7 | 30 | 40 | 1,200 |
| **Total** | | | **1,920** |

The cost is coarser hour-of-day data (3-hour bins) and slower back-catalog refresh.

## Other free options, for comparison

| Option | Free allowance | Fit |
|--------|----------------|-----|
| GitHub Actions, public repository | unmetered | chosen |
| Cloudflare Workers with cron triggers | 100,000 requests per day, short CPU time per run | fine for the pulse, too short for the snapshot and aggregation |
| Cloudflare Pages | unlimited static hosting, 500 builds per month | chosen host for the site |
| Cloudflare R2 | 10 GB storage | an alternative home for raw data in place of the private repository |
| A home machine or always-on device | — | most control, but not self-maintaining |

The recommendation is GitHub for the pipeline and data, Cloudflare Pages for the site,
and R2 as a fallback if a GitHub storage limit ever becomes a problem.
