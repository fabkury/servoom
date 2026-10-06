# Divoom community network: design

Design for the third servoom vertical, served at **servoom.pages.dev/community/**: a map
of the Divoom artist community built from who likes whose artworks, plus a neighbourhood
page per featured artist and a private "where do I sit" view for any artist who logs in
with the download tool. Nothing here is implemented. It builds on the statistics pipeline
([`../community-stats/`](../community-stats/README.md), live since 2026-10-05), whose
like event log is the main input, and on [`CLOUD_API.md`](../../CLOUD_API.md).

Decided on 2026-10-06, after the questions in the "Decisions" table below.

## The idea in one paragraph

Likes on Divoom are public, including who gave them. A like from one artist to another
is a weak social tie; thousands of them over a year form a graph whose structure (dense
groups, bridges, isolated corners) is the community's shape. The site computes that
graph once a day from likes given by people (never by the automated block), finds its
communities, lays it out on a 2D map, describes each community by what sets it apart
(country, canvas size, categories, hours of activity), and shows the flows between them.
Featured artists get a page showing their neighbourhood; everybody else is a dot.

## Decisions

| Topic | Decision | Why |
|-------|----------|-----|
| Naming | Same rule as `/stats/`: only **top artists** (Recommend picks, expert list, ambassadors, about 700 accounts) get a name, avatar or page. Everyone else is an unlabeled dot or a count. | One privacy policy for the whole site; nothing published that a takedown request could not undo. |
| Audience | Community members browsing: a map plus per-artist neighbourhoods. Behavioural findings (reciprocity rings, bridges, adoption of newcomers) go on the Studies page of `/stats/`. | A tool people return to, not a one-off report. |
| Nodes | **Uploaders only**: accounts with at least one public upload in the window. Accounts that only like are not nodes; they are summarised as each artist's and each community's *audience*. | A graph of all accounts is a star around popular artists. The artist-to-artist projection is where structure lives. |
| Edges | **Likes** build the graph and the communities. **Comments** (commenter to author) are logged from the start and shown as a second, thinner edge type on neighbourhood pages, not used for clustering (about 245 a day is too sparse). Tags, mentions and remix credits later. | Likes are the only tie available at scale. Follows are not readable for other accounts. |
| History | The forward like log (since 2026-10-05) plus a **one-time backfill** of the like lists of every artwork uploaded in the past 12 months. The backfill is interruptible and resumable at every step. | A usable map at launch instead of in a month; monthly windows for change over time. |
| Method | **Leiden** communities on the weighted artist graph of a rolling 12-month window; a spectral or node2vec embedding reduced with **UMAP** for the map. All computed in Python in the daily GitHub job, written as static JSON. The browser computes nothing but the ego view. | A force layout of 15,000 nodes is slow and unstable on phones; precomputed positions are identical for every visitor. |
| Placement | New path `/community/`, own entry on the landing page, own pages in the five site languages (en, es, zh, ja, ru) sharing `servoom-locale`. | `/stats/` is numbers, `/community/` is structure. |
| Artist lookup | Public neighbourhood pages for top artists only. Any other artist sees **their own** neighbourhood after logging in with the download tool's login; the data for that view is never published as a public file (see "The self view"). | Honours the naming rule while giving every artist a reason to visit. |

## What the data supports

| Tie | Source | Readable for other accounts | Volume | Time of the event |
|-----|--------|-----------------------------|--------|-------------------|
| Like | `Cloud/GetLikeUserList`, newest-first, 100 per page, token required | yes | ~16k a day raw, ~6k from people | pulse log: within the hour; backfill: unknown, bounded by the upload date |
| Comment | `Comment/GetCommentListV3`, anonymous | yes | ~245 a day | exact |
| Follow | `GetFansListV2`, `GetFollowListV2` | **own account only**; only `FansCnt`/`FollowCnt` per account | | |
| Playlist | `Playlist/GetSomeOneList` | yes | small | |
| Tag co-use, @mention, remix (`OriginalFileId`) | artwork records | yes | per artwork | upload time |

Node attributes (from the stats pipeline's current-state table and profile reads):
country and region, level, score, follower count, medals and ambassador badge, approximate
sign-up date from the sequential id, canvas sizes and categories uploaded, upload rhythm,
hours of activity, and whether Divoom features the account.

Two facts shape every step:

1. **The automated block** (even ids 400971852 to 400975850 and any range added to the
   stats exclusion list) gives about two thirds of all likes. It is removed before the
   graph is built. Left in, every method returns one giant star.
2. **Most likers never upload.** About 9,000 people like a recent upload in a month;
   about 1,700 upload. The projection onto uploaders keeps roughly a third of human
   likes as artist-to-artist edges, which is enough: on the order of 700,000 edges a year
   between some 14,000 artists.

## The graph

### Nodes

An artist is an account with at least one public upload inside the window. Three
windows are computed: the **map window**, rolling 12 months; **monthly windows**, one
per calendar month, for change over time; and the **all-time** window for neighbourhood
pages only. A node carries the attributes above plus degree figures, its community, its
map position and its audience summary.

### Edges

A like by artist A on an artwork by artist B is a directed event A → B, counted once per
(A, B, artwork) and only when A is not in the excluded ranges and A ≠ B. The raw weight
`n_AB` is the number of such events in the window.

For clustering and the map, the graph is undirected with weight

    w_AB = log(1 + n_AB) + log(1 + n_BA), divided by sqrt(deg_A · deg_B)

so that one devoted fan is not worth more than ten casual ones and popular artists do not
pull everything towards themselves. Neighbourhood pages use the directed raw counts and
show reciprocity: a pair is **mutual** when both directions exist in the window.

Comment edges are a separate table with the same shape (author, target, count, first and
last time) and are drawn, not clustered.

### Communities

Leiden (modularity, resolution chosen so that the median community has 100 to 300
artists; measured once and fixed in a config file) over the undirected weighted graph of
the map window. Communities smaller than **20 artists** are merged into a "small groups"
remainder and never get a page, so no small group of friends is identifiable.

Labels must not flip between days. Each day's communities are matched to yesterday's by
maximum member overlap (Hungarian assignment); a community keeps its id and colour while
at least half of its members stay. New ids are issued only for genuinely new groups. A
community gets an automatic descriptor from the attributes in which it differs most from
the whole (for example "16×16 · China · Character", "64×64 · Europe · Nature · evenings")
and, optionally, a hand-written name in the config file.

What is published per community: member count, share of top artists, the descriptor,
country mix, size and category mix, hour-of-day profile, audience size and where it comes
from, internal density, likes given to and received from each other community, and the
list of its **top artists** only.

### Map

UMAP (cosine metric) on the rows of the normalised adjacency, lightly supervised by the
Leiden labels (`target_weight 0.3`) so communities form readable patches, with a fixed
random seed and initialised from yesterday's positions so the map drifts rather than
jumps. A spectral embedding followed by UMAP was tried first on 2026-10-06 and gave a
thin curve; igraph's DrL and Fruchterman-Reingold layouts collapsed the giant component
into one ball. Output: one position per artist, in a compact binary file
(Float32 x, y; Uint16 community; Uint8 size class; Uint32 id only for top artists).

### Audience

For each artist and each community, likers who are not uploaders are counted, never
listed: distinct likers in the window, countries, share that also like other members of
the same community, share that are brand new accounts, repeat rate. These are the figures
that say whether a community has a public of its own or only likes itself.

### Time

The pulse log gives the exact hour of every like since 2026-10-05. The backfill does not:
a like list has positions, not times. Backfilled likes are dated by the **upload month of
the artwork**; the stats site already measures that most lifetime likes arrive in the
first days, so the error is small for monthly windows and nil for the map window. The
monthly history pages mark the months that rely on backfilled, approximately dated edges.

## Data flow

```
 servoom-raw (private)                     servoom-stats (public, daily job)
 obs/pulse/**/HH-likes.parquet  ──┐
 obs/likes-backfill/*.parquet   ──┼──►  build artist graph (12 months, monthly)
 obs/comments/**                 ──┤      remove excluded ranges, project to uploaders
 state/current.parquet (authors)──┘      Leiden, match to yesterday, embed, UMAP
                                          audience summaries, per-top-artist egos
                                                   │
                                                   ▼
                                       data/community/*.json, map.bin
                                       data/community/artists/<id>.json  (top only)
                                       data/community/self/<hash>.json.enc (all)
                                                   │ commit + deploy hook
                                                   ▼
                                       servoom (docs/public/community/*.html)
                                       built on Cloudflare Pages, data pulled at build
```

The graph step is appended to the existing snapshot job after its aggregation, or run as
its own daily job after the snapshot finishes. Expected cost: reading a year of like
rows (a few million) and running Leiden and UMAP on 15,000 nodes and a few hundred
thousand edges takes a few minutes on a standard runner. Libraries: `igraph` with
`leidenalg`, `scipy` for the spectral embedding, `umap-learn`, all pip-installable.

## The backfill

Purpose: like lists of every artwork uploaded in the 12 months before the log began, so
that the map is complete at launch. Run once, by hand, in several sessions.

| Step | Detail |
|------|--------|
| Work list | From the current-state table: public artworks with upload date in the window and `LikeCnt > 0`, ordered by `GalleryId`. About 120,000 artworks. |
| Per artwork | Page `Cloud/GetLikeUserList` from position 1 until a page is short or the position passes `LikeCnt`. Most artworks need one page; the mean is near 1.3. |
| Requests | About 117,000 in total (measured 1.07 per artwork on a sample). At 4 per second from one pool account, 8 to 9 hours, so two or three job runs of at most 4 hours each. |
| Output | `obs/likes-backfill/<gid-range>.parquet`, append-only, rows `(gid, position, liker, observed_at)`; `auto` flagged as in the pulse log. One file per 2,000 artworks. |
| Checkpoint | Branch `state-backfill` of the raw repository, one force-pushed commit holding `{next_gid, done_count, started_at, finished_at}`. Written after every file, i.e. every 2,000 artworks or about 10 minutes. |
| Resumable | A run starts from `next_gid`. A file is written atomically (temp name, then rename, then push) so a kill between two checkpoints loses at most the partial file, which the next run re-reads. Re-reading an artwork is idempotent: rows are keyed by `(gid, position)` and the newer observation wins. |
| Interruptible | `SIGTERM` and `workflow_dispatch` cancellation flush the current file and write the checkpoint before exiting. The job also stops itself at a wall-clock budget (`MAX_MINUTES`, default 240) and on the stats pipeline's circuit breaker (repeated HTTP errors, `ReturnCode 11`). |
| Scheduling | `workflow_dispatch` with inputs `max_minutes` and `rate`; an optional nightly cron that exits immediately when `finished_at` is set. Never concurrent with the snapshot on the same account: the backfill uses `spare-01`. |
| Dedupe | Backfilled rows for artworks already in the pulse log are merged by `(gid, liker)`; the pulse row, which has a time, wins. |
| Verify | Done 2026-10-06, see "Checked" below: like lists page to the end and match `LikeCnt` within a few entries. |

The backfill is also the recovery path after a long pulse outage: run it over the
missing days.

## The self view

A logged-in artist who is not a top artist can see their own neighbourhood. The
constraint: the data for all 14,000 artists must exist somewhere the browser can reach,
without being a public lookup table of account ids.

Chosen mechanism, in order of preference, to be confirmed by a prototype:

1. **Encrypted per-artist files plus a small verifier.** The daily job writes
   `data/community/self/<H(id)>.json.enc` for every artist, encrypted with a key derived
   from the artist's id and a secret `SELF_KEY` held in GitHub and in a Cloudflare
   Worker. The file name uses a keyed hash, so the public files reveal neither ids nor
   counts. The download tool, after its usual Divoom login, sends `UserId` and `Token`
   to the Worker; the Worker proves ownership by calling one token-gated Divoom command
   for that account (`GetMyLikeListV3` with those credentials answers only for the
   token's owner) and returns the file name and key for that id only. The browser fetches
   and decrypts the file. The Worker stores nothing and logs nothing beyond its counters.
   It is the same kind of Worker as the existing `servoom-stats-trigger`.
2. **Fallback: public per-artist files keyed by raw id**, if the Worker proves
   troublesome. Ids are public on Divoom and the files contain no names, but anyone
   could then look up anyone, which is the option that was declined. Not the plan.

What the self view shows: the artist's community and descriptor, their position on the
map (highlighted dot), artists they like most and who like them most, mutual pairs, their
audience summary, and how these moved month by month. Neighbours that are top artists are
named; others are dots with community colour only. The view may resolve a neighbour's
public profile live through the visitor's own Divoom session, since that is the visitor's
own request to Divoom and nothing is published by the site. Whether to offer that is left
to the implementation.

## Pages (`/community/`)

All pages in the five languages, light and dark themes, readable on a phone, with a
table behind every chart, as on `/stats/`.

| Page | Content |
|------|---------|
| `index.html` Map | The 2D map on a canvas: every artist a dot coloured by community, top artists labelled on zoom, hover shows community and size class, click on a top artist opens their page. Side panel: the community list with member counts and descriptors. A month slider is **not** on the map (positions are for the 12-month window only). |
| `communities.html` | One card per community: descriptor, size, country and size mix, audience, density, its top artists with avatars. Sorted by size. |
| `community.html?id=` | One community in full: the figures above, hour-of-day profile, likes given to and received from other communities (a small chord diagram), members over time, top artists. |
| `flows.html` | Likes between communities and between countries as a chord diagram and a matrix, for the map window and per month. |
| `artist.html?id=` | A top artist's neighbourhood: ego graph (one hop, two hops behind a toggle) drawn in the browser with a force layout of at most a few hundred nodes, named neighbours only if top artists, mutual pairs, comments overlay, audience summary, community membership over time. Linked from and to their `/stats/` page. |
| `history.html` | Community sizes per month, newcomers adopted per community, share of likes that stay inside a community, reciprocity share. |
| `me.html` | The self view: a login box reusing the download tool's session, then the artist page layout for the visitor's own account. |
| `methods.html` | How the graph is built, what is excluded, what "community" means, the dating of backfilled likes, the naming rule, how to be removed. |

Sizes shipped to the browser: the map binary for 15,000 artists is about 200 KB; the
community file a few hundred KB; a top artist's ego file 10 to 50 KB. Nothing requires
loading the whole edge list.

Charts use the vendored d3 already under `docs/public/stats/vendor/`; the map and the
ego view are plain canvas and d3-force. No new dependency on the site.

## Privacy

* Names, avatars and pages only for top artists, as on `/stats/`; one shared exclusion
  list honoured by both verticals; removal on request through an issue.
* Communities under 20 artists are never shown individually. Audience figures are
  counts. Hour-of-day and country profiles are published only per community and per top
  artist, never per anonymous dot, so a dot cannot be matched to an account by its
  attributes. Dots carry community and size class only.
* The map shows positions without ids. Hovering a non-top dot shows its community, nothing
  else.
* The self view is served only to the account that owns it, through a verifier that keeps
  nothing.
* Raw like rows and the per-artist files stay in private storage; the public repository
  gets aggregates, top-artist files and encrypted self files only.
* The methods page states, in neutral wording, that likes from automated accounts are
  excluded and how.

## Storage

Private repository (`servoom-raw`):

```
obs/likes-backfill/<gid-range>.parquet      one-time backfill rows
state-backfill (branch)                     checkpoint, one commit
state-graph (branch)                        yesterday's communities and positions, for matching
```

Public repository (`servoom-stats`), `data/community/`:

```
map.bin                      positions, community, size class per artist (binary)
communities.json             one row per community (window + per month)
flows.json                   community × community and country × country matrices
history.json                 monthly series
artists/index.json           top artists with community and degree figures
artists/<id>.json            ego data for one top artist
self/<keyed hash>.json.enc   encrypted self-view files, one per artist
config/graph.toml            resolution, minimum community size, seeds, hand names
status.json                  last run, windows covered, backfill coverage
```

## Checked on 2026-10-06

Run with `spare-01` from the owner's machine (one login; the token stayed in a scratch
folder), against the live like log (37 hours, 33 pulse files and one snapshot) and a
stratified sample of 2,982 artworks of the 12-month window, about 230 per month, whose
like lists were read in full (3,183 requests, 13 minutes at 4 per second). Scripts and
the sample stayed outside the repository.

| Assumption | Result |
|------------|--------|
| `GetLikeUserList` pages past 1,230 entries | **Yes.** The most liked artwork of the window (`LikeCnt` 1,707) returned 1,704 entries over 18 pages with `ReturnCode 0` throughout. 31 of them were repeats of the same liker, so rows are deduplicated by `(gid, liker)` as planned. |
| The verifier call | **Works.** `GetMyLikeListV3` answers `ReturnCode 0` with the account's own token and `11 "Token is not match"` with a wrong token or with another account's `UserId`; with no credentials, `3 "Request data is incomplete"`. `GetMyUploadListV3` behaves the same. Not yet tried from a Worker's IP address. |
| Backfill request count | **Smaller than estimated.** The window holds 109,842 public artworks with at least one like, mean 22 likes, 116,943 pages in total; only 10 artworks exceed 1,230 likes. The sample needed 1.07 requests per artwork, so the whole backfill is about **117,000 requests, 8 to 9 hours at 4 per second**: two or three runs of 4 hours. |
| Share of automated likes by upload month | 18% for October 2025 uploads, rising to 50 to 55% for March to June 2026 and 40 to 48% since; 41% over the sample. Older artworks have fewer block likes than the day-to-day flow suggests, so backfilled months are less distorted than feared. |
| Likers who are uploaders | **54%** of human likes in the sample come from accounts with an upload in the window (the design assumed a third). The artist-to-artist projection keeps more than half of the human signal. |
| Edges are dense enough | The 2.7% sample alone gives an artist graph of 3,007 nodes and 12,575 undirected edges with a giant component of 98%, 967 mutual pairs and 3,382 pairs with more than one like. Scaled to the full window the graph has on the order of 14,000 nodes and 400,000 to 500,000 edges. |
| Communities exist | **Only with degree normalisation.** With raw log-weights Leiden returns one community of 93% of the nodes at every resolution (modularity 0.02 to 0.35): a few hundred super-likers, the top 1% of human likers giving 35% of human likes, tie everything together. With the design's degree-normalised weight the same graph gives, at resolution 1.0, 37 communities of 20 or more members covering 96% of nodes, largest 352, median 54, modularity 0.68 against 0.49 for a degree-preserving shuffle. At resolution 0.5 one community still holds half the nodes. So the normalisation stays, and the resolution is tuned on the full graph starting from 1.0. |
| Communities are stable | **Not established.** Splitting the sample's artworks into two random halves (each 1.35% of the window) and clustering each gives P(same community in the second half, given same in the first) of 0.33 against a base rate of 0.22: better than chance, but each half is far too thin. The real check runs on two consecutive days once the backfill exists, as planned. |
| UMAP fits the job | 32-dimensional spectral embedding plus UMAP took 39 seconds for 3,007 real nodes and 41 seconds for a synthetic 15,000-node graph with 250,000 edges on the owner's machine; Leiden took 1.4 seconds. Well inside a daily job. |
| Pool account for the backfill | `spare-01` logged in and read 3,183 like lists; its health is unchanged. |

Consequences for the design, already applied above: the edge weight keeps both-sided
degree normalisation; the backfill plan says 117,000 requests over two to three runs;
like-list rows are deduplicated; super-likers get an explicit treatment on the methods
page (they are the reason a plain like count does not define neighbourhoods).

Still to check, needing the backfill or a deployed Worker: day-to-day community
stability, the resolution that gives a median community of 100 to 300 artists, and the
verifier call from a Worker's IP address.

## Order of work

1. Checks above, on the live log, in a scratch notebook. Decide spectral versus node2vec
   and the resolution from what the first graph looks like.
2. Backfill collector in `servoom-stats` (`stats/backfill_likes.py`, workflow
   `backfill.yml`), run to completion over several evenings.
3. Graph job: build, exclude, project, Leiden, match, embed, audience; publish
   `data/community/`. Run daily after the snapshot.
4. Pages: map and communities first, then flows and history, then top-artist pages.
   Landing page entry and the five languages from the first page on.
5. The self view: Worker verifier, encrypted files, `me.html`.
6. Comments overlay, then the Studies entries on `/stats/` (reciprocity rings, bridges,
   newcomer adoption), then tags and remix links as further edge types.

## Status

* **2026-10-06, backfill started.** `stats/backfill_likes.py` and workflow `backfill.yml`
  in `servoom-stats` (commit 88fbd45). Work list fixed at 110,195 artworks dated
  2025-10-05 to 2026-10-05 01:23 UTC (when the pulse log began), 117,341 pages expected.
  Two one-minute local runs proved the checkpoint and resume; the first Actions run
  (`workflow_dispatch`, 235 minutes, 8 requests per second) polled about 480 artworks a
  minute. A daily fallback cron at 10:27 UTC continues it until `finished_at` is set.
  Files: `obs/likes-backfill/<first>-<last>.parquet`, rows `(gid, pos, liker, t, auto)`;
  readers deduplicate by `(gid, liker)`.
* **2026-10-06 20:09 UTC, backfill finished.** 110,195 artworks, 117,481 requests, 57
  files, two Actions runs (235 and 12 minutes) at 8 requests per second. `spare-01` is a
  spare again. The daily cron of `backfill.yml` now exits at once; it stays as the
  recovery path after a long pulse outage (clear `finished_at` and set a new work list).
  Found on the way: a shallow clone of the raw repository loses its merge base when more
  than 20 commits land during a run, which broke the day's snapshot at its final push;
  `rawrepo.push_main` now deepens the clone (servoom-stats 174a861).

* **2026-10-06, graph job built.** `stats/graph.py` + `graph.yml` in `servoom-stats`
  (runs after the snapshot or at 09:27 UTC; no Divoom requests). First full run: 10,339
  artists, 134,487 edges, 12,493 mutual pairs, 82 seconds. The resolution rule changed:
  the median-size target alone chose 0.5, where one community held 75% of artists, so
  the rule now requires the largest community under 15% of nodes and then the median
  closest to 150; that pinned **1.5** (56 communities of 20 or more, largest 1,156,
  median 76, modularity 0.50 against 0.36 for a degree-preserving shuffle). Published
  under `data/community/`: `communities.json`, `flows.json`, `history.json`,
  `artists/<id>.json` for the 472 top artists in the graph, `map.bin` (id-free dots,
  shuffled order), `config.json` (pinned resolution and the trials), `status.json`.
  Day-to-day stability is measured from the second run on (`status.stability`).
  Audience country mix is not available: likers' countries are not stored. Pages next.

* **2026-10-06, pages built.** `docs/public/community/` in servoom: map, communities,
  community, flows, artists, artist, history, methods, in the five languages, sharing
  `stats.css`, `i18n.js` and the vendored d3/Plot; `community.js` draws the map on a
  canvas (zoom, hover, labels for top artists), chord diagrams and the ego graph. The
  landing page and the stats pillar navigation link to it. Not built: the self view.

## Still open

* Whether to resolve neighbours' names live in the self view through the visitor's own
  Divoom session.
* Hand-written community names: who writes them and in which languages (the automatic
  descriptor is translatable from its parts; a hand name is not).
* Whether the all-time window is worth its cost on top-artist pages, or 12 months is
  enough everywhere.
* Comment edges weighting, if they ever join the clustering.
