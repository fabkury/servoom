# Divoom artist like-network: design

The third servoom vertical, served at **servoom.pages.dev/artists/**: who likes whose
work on Divoom, browsable from featured artist to featured artist. It builds on the
statistics pipeline ([`../community-stats/`](../community-stats/README.md)), whose like
event log is the input, and on [`CLOUD_API.md`](../../CLOUD_API.md).

## History of the design

* **2026-10-06.** Designed and built as a *community map*: Leiden communities on the
  artist like-graph, a UMAP map, community pages, flows between communities and
  countries, plus artist pages. Checks, backfill and pages are recorded below under
  "Record of 2026-10-06".
* **2026-10-07, decision.** The detected communities were arbitrary, mostly nameless
  (two of the three largest had no distinctive trait) and not useful to browse: the
  notion generated more noise than signal. Communities, the map and the flows were
  removed. What stays is the part that worked: measuring likes between artists and
  navigating artists by their "liked most by" and "likes most" links. The section moved
  from `/community/` to `/artists/` (with a redirect).

## What it is now

| Topic | Decision |
|-------|----------|
| Naming | Same rule as `/stats/`: only **top artists** (Recommend picks, expert list, ambassadors, about 1,300 accounts) get a name, avatar or page. Everyone else is counted, never listed. |
| Nodes | Uploaders only: accounts with at least one public upload in the rolling 12-month window. Accounts that only like are each artist's *audience*, a count. |
| Edges | A like by artist A on a work by artist B, counted once per (A, B, artwork), automated ranges removed, self-likes removed. Directed counts; a pair is *mutual* when both directions exist in the window. |
| History | The forward like log (since 2026-10-05) plus the one-time 12-month backfill. Backfilled likes carry no time and are dated by the artwork's upload month. |
| Pages | `/artists/` directory (featured artists, sortable, searchable), `artist.html#id` (tiles, "liked most by" and "likes most" with featured artists named and the rest folded into one row, mutual featured artists, likes per month), `history.html`, `methods.html`. Five languages. |
| Job | `stats/network.py` in servoom-stats, workflow `network.yml`: runs after the snapshot or at 09:27 UTC, no Divoom requests, about 45 seconds, publishes `data/network/` and calls the deploy hook. |
| Not built | The self view for non-featured artists (encrypted per-artist files unlocked by a Worker that verifies the Divoom token). Comment edges. |

### Published files (`data/network/`)

```
status.json              artists, pairs, mutual pairs, likes in the window, build time
history.json             per month: likes between artists, active artists, pairs, mutual share, newcomers, newcomers liked
artists/index.json       featured artists with in/out degree, likes received/given, mutual, audience, country
artists/<id>.json        one featured artist: tiles, named neighbours (top 25 per direction) + others folded, mutual featured, months
```

### Privacy

Names, avatars and pages only for top artists; one shared exclusion list with `/stats/`;
removal on request through an issue. Non-featured neighbours appear only as "N other
artists, M likes". Raw like rows stay in the private repository.

## Record of 2026-10-06

Kept for reference; the community parts are no longer on the site.

### Checks

Run with `spare-01`, against the live like log (37 hours) and a stratified sample of
2,982 artworks of the 12-month window whose like lists were read in full.

| Assumption | Result |
|------------|--------|
| `GetLikeUserList` pages past 1,230 entries | Yes: 1,704 of 1,707 entries over 18 pages. A few likers repeat in one list, so rows are deduplicated by `(gid, liker)`. |
| The verifier call for a future self view | `GetMyLikeListV3` answers `ReturnCode 0` with the account's own token and `11 "Token is not match"` with a wrong token or another account's `UserId`. |
| Backfill size | 109,842 liked artworks, 1.07 requests each, about 117,000 requests. |
| Automated share by upload month | 18% for October 2025 uploads, 50 to 55% for March to June 2026, 40 to 48% since. |
| Likers who are uploaders | 54% of human likes come from accounts with an upload in the window. |
| Communities | Only with degree-normalised weights; on the full graph the median-size rule picked a resolution with one 75% blob, a largest-under-15% rule gave 56 communities, modularity 0.50 against 0.36 shuffled. A spectral embedding + UMAP gave a thin curve; supervised UMAP gave readable patches. All removed on 2026-10-07. |

### Backfill

`stats/backfill_likes.py` + `backfill.yml` (servoom-stats): work list fixed on the first
run on branch `state-backfill` (110,195 artworks dated 2025-10-05 to 2026-10-05 01:23
UTC); chunks of 2,000 artworks pushed as `obs/likes-backfill/<first>-<last>.parquet`
before the checkpoint is force-pushed; SIGTERM, a wall-clock budget and a token refusal
flush and checkpoint; finished 2026-10-06 20:09 UTC after 117,481 requests in two runs
at 8 requests per second. The daily cron now exits at once; it is the recovery path
after a long pulse outage (clear `finished_at`, set a new work list). Readers
deduplicate by `(gid, liker)`.

Found on the way: a shallow clone of the raw repository loses its merge base when more
than 20 commits land during a run, which broke that day's snapshot at its final push;
`rawrepo.push_main` now deepens the clone.

## Still open

* The self view (Worker verifier, encrypted files, `me.html`).
* Comment edges as a second relation on artist pages.
* Whether the directory should also list non-featured artists in aggregate (for example
  by country), which the naming rule allows.
