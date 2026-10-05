# A. What the site shows

A single crawl gives counters as they stand on one day. Repeated polling gives three
things a single crawl cannot:

* **Flows.** Likes, views, comments, uploads and sign-ups per hour and per day, measured
  as differences between snapshots. The 2026-10-04 study had to estimate most of these.
* **Events with a time.** When an artwork was promoted, re-filed, hidden or deleted, and
  what its counters did before and after.
* **Trends.** Whether any of the above is growing, shrinking or seasonal.

Each section below is one page of the site. *Needs* says which collection job feeds it
(see `02-engineering.md`).

## 1. Pulse (home page)

The current size of the community and its direction.

| Figure | How it is measured | Needs |
|--------|--------------------|-------|
| Public uploads per day | new `GalleryId`s seen in listings | pulse |
| All uploads per day, public or not | advance of the highest `GalleryId` | daily |
| Share of uploads that stay public | ratio of the two above | daily |
| New accounts per day | advance of the highest `UserId`, times the share of ids in use | daily |
| Likes per day, from people and raw | counter differences; split by like-list sampling | pulse + daily |
| Views per day | counter differences | pulse + daily |
| Comments per day | `CommentCnt` differences and comment lists | daily |
| Active uploaders (1, 7, 30 days) | distinct uploaders in the window | daily |
| Active likers (7, 30 days), estimated | distinct accounts in sampled like lists | daily |

Each figure shows today's value, a 7-day average, and a line over all collected history.

## 2. Rhythm

* Hour-by-weekday heatmaps of uploads, likes and views (UTC, with a selector for a few
  time zones). Shows where the audience lives and when to post.
* The same heatmap for curator promotions, which shows the curators' working hours.
* Seasonality once a year of data exists: the December to January peak seen in 2025, and
  whether sign-ups lead uploads (new device owners start uploading some weeks later).

## 3. Life of an artwork

* **Attention curve.** Likes and views per hour over the first 30 days, per day over the
  first 6 months, as a median band by upload cohort. From it: the half-life of an upload
  and the share of lifetime likes that arrive in the first day, week and month.
* **Time to first like**, from people and from any account.
* **Survival.** Share of public uploads still listed after 1, 7, 30 and 365 days.
  Disappearance means deleted, made private or hidden; the API does not say which.
* **Back catalog.** Likes and views per day reaching artworks older than one year, and
  whether that long tail is growing.

## 4. Curation

* Promotions per day into NEW and Recommend.
* Odds of promotion by canvas size and category, as a time series.
* Delay from upload to promotion.
* **Promotion effect.** Hourly counters around the moment an artwork enters Recommend,
  compared with unpromoted artworks of the same age and prior counters. The 2026-10-03
  study could only compare totals after the fact.
* Re-filing: how many Default uploads curators move into a topic category.
* Size of the review queue (`Classify 21`) and how long uploads wait in it.

## 5. Canvas sizes and formats

* Share of uploads, likes and views by canvas size over time (16, 32, 64, 128, 256).
* Median likes and views per artwork by size, for monthly cohorts.
* Photo share and AI-category share of uploads over time.
* Uploads with layers, music or copyright flag over time, as a proxy for which app
  features people adopt.

## 6. Artists

Aggregate part, no names:

* New uploaders per week and how many upload again within 30 and 90 days (retention
  cohorts).
* Concentration: share of likes going to the top 1% and 10% of uploaders, monthly.
* Uploaders by country over time. Cells with fewer than 5 accounts are merged into
  "other".

Named part, top artists only (see "People" below):

* Most liked this week and this month, counting likes from people only.
* Rising artists: largest gain in followers or in weekly likes.
* Recommend picks per artist, updated daily, continuing the 2026-10-03 table.
* Per-artist page: uploads per month, likes and views per upload, follower count over
  time, promotion rate.

## 7. Audience

* Distinct likers per day, week and month, measured from the like event log, and how
  many are uploaders themselves.
* Country mix of likers over time.
* Country mix of new accounts, from a daily sample of newly issued ids.
* Comments: commenters per week, share of comments written by the top five commenters.

## 8. Events and topics

* Contest participation: entries per day in the current Pixel Match (`Classify 30`), per
  contest.
* Tags: fastest-growing tags by weekly gain in `GalleryCnt`.
* Category sizes over time, including the hidden ones (`CLOUD_API.md` table).
* Official forum posts: views, likes and comments per post over its first two weeks.

## Added pages and figures

`06-enhancements.md` adds the following; each is specified there.

| Where | Addition |
|-------|----------|
| Pulse | all uploads against public uploads; markers for app releases, contests and promotions on every time series; history back to 2018, reconstructed |
| Life of an artwork | survival split into deleted, hidden and made private; review queue waiting time and approval rate |
| Audience | measured daily, weekly and monthly active likers; liker retention; reciprocity; the sign-up funnel (share of new accounts that like, upload or comment) |
| Artists | how levels and scores seem to be earned |
| Events and topics | trending tags from uploads; remix chains; dedications; languages |
| New page: Formats | container formats, animation length, palettes, layers and music, duplicate uploads |
| New page: Popular | how long artworks stay in the Popular tab and what predicts entry |
| New page: Studies | whether a higher like count attracts more likes from people |
| Download tool | where a user's own artworks fall against community percentiles |

## 9. Methods

One page that says how every figure is produced, and that carries the correction for
automated likes:

* What "likes from people" means: likes from accounts outside the known automated block
  (even ids 400971852 to 400975850), estimated from like-list samples.
* One chart: raw likes per day against likes from people per day.
* The detection rule that watches for new automated ranges (see `02-engineering.md`,
  "Automated-account detection"), and a dated note whenever the excluded set changes.
* Known gaps: who views is not visible, private uploads are not counted, sampling error
  on back-catalog figures.
* A status box: time of the last successful pulse and snapshot, and any gap in the data.

The site uses neutral wording ("automated accounts") and does not say who operates them.

## People

* A **top artist** is an account that Divoom already features: at least 3 Recommend picks
  in the past 12 months, or presence in `GetExpertListV4`, or an ambassador badge. Only
  these get a name, a leaderboard row or a page.
* Everyone else appears in counts only. No user id, name or avatar of other accounts is
  published, and none is committed to the public repository.
* An artist can ask to be removed by opening an issue; the pipeline keeps an exclusion
  list in the public repository.
* The site rehosts one kind of image: the **avatar of each top artist**, decoded from
  Divoom's pixel format and stored as lossless WebP. No artworks are rehosted;
  leaderboards show avatar, name and numbers. An artist removed on request loses the
  avatar file too.

## Insights that only appear with time

| Question | First answerable after |
|----------|------------------------|
| What time of day gets the most views per upload? | 2 weeks |
| How much does a Recommend pick add, hour by hour? | 1 month |
| Do new uploaders stay? | 3 months |
| Is the community growing? | 3 months for a trend, 12 for seasonality |
| Is automated liking rising or falling? | 1 month |
| Do device launches or sales show up as sign-ups? | at the next one |
| How many uploads are deleted, and how fast? | 1 month |
