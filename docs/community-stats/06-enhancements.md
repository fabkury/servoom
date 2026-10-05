# Enhancements: using everything the crawls can give

Added 2026-10-04 after a review of what the design left unused. All twelve items below
are adopted. Where this document adds requests, storage or pages, it extends
`01-content.md`, `02-engineering.md` and `05-servoom-umbrella.md`; totals in those
documents have been updated to include it.

## Summary

| # | Enhancement | Extra requests per day | New raw data | New on the site |
|--:|-------------|-----------------------:|--------------|-----------------|
| 1 | Like event log | 0 to 300 | one row per like | measured active likers, liker retention, reciprocity |
| 2 | Sign-up funnel | 0 | account table | activation of new accounts |
| 3 | Tags, mentions, remix links | 0 | per-artwork text table | topics, remix chains, dedication network |
| 4 | Comment fingerprints | 0 | hash, length, language | automated-comment detection, languages |
| 5 | Artwork files | about 350 | per-file features | formats, animation, palettes, duplicates |
| 6 | Every upload, listed or not | about 1,300 | all-uploads table | true upload count, review queue, why artworks vanish |
| 7 | Popular ordering | about 950 | rank snapshots | what rises in Popular |
| 8 | Divoom's calendar | about 10 | events table | annotations on every chart |
| 9 | Social-proof analysis | 0 | — | one methods-grade study page |
| 10 | Level and score rules | 0 | — | "how points are earned" |
| 11 | Reconstructed history | 0 | — | charts back to 2018 from day one |
| 12 | Personal benchmarks | 0 | — | percentile tables used by the Download tool |

About 2,900 more requests a day, on top of 78,000.

## 1. Like event log

The snapshot reads the like list of every artwork liked in the past 24 hours, and the
pulse does the same hourly for the 30-day window. Lists are newest-first, so the first
*n* entries, where *n* is the rise in `LikeCnt`, are exactly the new likes.

* Store each as an event: `(gallery_id, liker_id, observed_at, window_start)`. The time
  of a like is known to the hour inside the pulse window and to the day outside it.
* When *n* exceeds 100, page further so no like is missed (rare; a few hundred extra
  requests on a busy day).
* A falling `LikeCnt` is recorded as unlikes, without identity.
* Roughly 16,000 events a day, about 100 KB compressed.

What it gives, all as aggregates: daily, weekly and monthly active likers (measured, no
longer estimated); likers retained week over week; likes per liker; share of likes that
are reciprocated between two uploaders within 30 days; the split between people and
automated accounts on every like, not a sample.

## 2. Sign-up funnel

Account ids rise with sign-up date, and the daily frontier reading maps id to date
exactly from launch onward (approximately before, from first-upload dates).

* A private account table: `user_id`, estimated sign-up date, region parity, first like
  seen, first upload seen, first comment seen.
* Site: for each sign-up week, the share of accounts that liked, uploaded or commented
  within 1, 7, 30 and 90 days, and the median delay. The denominator comes from the
  frontier and the daily 200-id existence sample.
* Limit: a like on an artwork older than 30 days is timed to the day; an account that
  only views is invisible.

## 3. Tags, mentions and remix links

Each artwork record already carries `FileTagArray`, `AtList` and `OriginalGalleryId`.
The collector stops discarding them.

* Private table `obs/artwork_meta/`: gallery id, tags, mentioned user ids, original
  gallery id, title and caption language codes, title and caption lengths. Titles and
  captions themselves are not stored.
* Site:
  * Trending tags by uploads and by likes from people, weekly and monthly. A tag is
    published only if at least 5 different uploaders used it.
  * Remix: share of uploads that are remixes, and the most remixed artworks (named only
    when the original is by a top artist).
  * Mentions: how often uploads are dedicated to someone, and the dedication network
    among top artists.
  * Languages of titles and captions over time.

## 4. Comment fingerprints

For every comment read: a salted hash of the normalised text, its length, a language
code, and the `RobertFlag`. No text.

* Detection: the same hash from many accounts, or one-comment-per-account bursts from
  neighbouring ids, flags a campaign. Like the like-range detector, it opens an issue
  and never excludes anything by itself.
* Site: comments from people against automated comments, comment languages.

## 5. Artwork files

About 320 public uploads a day. Files are served by `f.divoom-gz.com` without a token.
The snapshot downloads each new upload once, decodes it with servoom's decoders, stores
derived features and throws the pixels away. Nothing is rehosted.

| Feature | Use |
|---------|-----|
| Container format id, file size | format adoption (`FILE_FORMATS.md`) |
| Width, height, frame count, speed, total duration | stills against animations, animation length |
| Colours used, share of transparent or black pixels | palette trends by canvas size |
| Layer file present, layer count; music present | feature adoption |
| Exact hash of the decoded frames | re-uploads of the identical picture |
| 64-bit difference hash of the first frame, plus one of a mid frame for animations | near-duplicates: recolours, small edits, crops |

**Cost of hashing.** A difference hash shrinks the frame to 9 by 8 grey pixels and
compares neighbours: microseconds per image. Decoding dominates, at tens of
milliseconds for most files and up to about a second for a long 256-pixel animation, so
a day's uploads take a minute or two. Matching a day's 320 hashes against a few million
stored 64-bit hashes is one vectorised XOR and bit count, a few seconds. For 16 by 16
art the exact hash does most of the work, since the image is barely larger than the
perceptual hash; the difference hash matters for 64 pixels and up.

**History.** Duplicates can only be found against files already hashed. At launch that
is nothing, so duplicate rates start as "among uploads since launch". An optional
one-time backfill would download and hash the existing 1.54 million files: about 2 days
at 8 requests per second, run in resumable chunks over a few weeks. It is worth doing
but not required for launch.

Site: format and feature adoption over time; animation length distribution; palette
sizes; share of uploads that duplicate an earlier upload by someone else, in aggregate,
never naming accounts.

## 6. Every upload, listed or not

`Cloud/GalleryInfo` (token needed) answers for artwork ids that appear in no listing:
uploads held for photo review, removed uploads (`IsDel 1`) and other accounts' private
uploads (`PrivateFlag 1`, `IsDel 8`). It answers `ReturnCode 1` past the newest id. Most
new artworks get odd ids, but about 14% of even ids exist too. In a 400-id sample two
days old, 77% were public, 5% private, 4% removed and 14% had no record.

* **Hourly id walk** in the pulse: request every id from the last known frontier until
  40 in a row are missing. About 50 requests an hour.
* **Follow-up**: unlisted ids are re-read daily for a week to record the review outcome
  (`CheckConfirm` 1 to 2 or 3) and the waiting time.
* **Vanished artworks**: when an artwork drops out of the listings, one `GalleryInfo`
  call records whether it is deleted, hidden or private. About 100 a day.
* **Private uploads are counted and nothing more.** For a record with `PrivateFlag 1`
  the collector keeps the id, the flags and the upload hour, and discards everything
  else, including the uploader id and the file id. Their files are never downloaded.
  That any logged-in account can read these records is a weakness on Divoom's side; the
  site reports only the daily count of private uploads.

Site: all uploads per day against public uploads; review queue length, waiting time and
approval rate; survival curves split into deleted, hidden and made private.

## 7. Popular ordering

`FileSort 1` is the Popular tab. Each pulse reads its first 3 pages for the Recommend
feed, the NEW feed and the six largest categories, at each of the 5 canvas sizes: about
40 requests an hour after merging small lists. The order drifts between calls
(`CLOUD_API.md`), so ranks are kept as observed and analysed in bands, not exact
positions.

Site: time an artwork stays in the top 30 and top 90; what predicts entry (likes from
people, raw likes, views, age, tier); whether automated likes move an artwork up. The
page states plainly that this is an inferred description, not Divoom's algorithm.

## 8. Divoom's calendar

Once a day, one request each: `Cloud/GetMatchInfo`, `Discover/GetTheme`,
`Discover/GetTopNew`, `Discover/GetAlbumListV3`, `Forum/GetList` (first page per
region), `Mall/GetListV2`, `GetStoreV2`, `GetGalleryAdvert`, `Lottery/Announce`. All
answered without a bound device on 2026-10-04. `GetNewAppVersion` returned only
`Version 1` with the fields tried, so app releases are left out until its request is
worked out.

* Private `obs/calendar.csv`: date, kind (app release, contest start, theme, album,
  forum post, promotion), label.
* Site: every time-series chart can show these as markers, and the events page lists
  them with the change in sign-ups and uploads over the following 7 days.

## 9. Does a like count attract likes?

Automated likes land on almost every artwork in small random amounts. Among artworks of
the same age, tier, canvas size and view count, some happen to have received more of
them. Comparing later likes from people between those groups estimates whether a higher
displayed count draws more real likes.

* Uses only the like event log; no new requests.
* Published as a study page with its method, sample sizes and uncertainty, updated
  monthly. It is observational: automated likes are not fully random (they rise with
  views and tier), so the page reports the comparison within narrow strata and says
  what could still confound it.

## 10. How levels and scores are earned

The snapshot already reads `Level`, `Score` and `LookScore` for top artists daily. A
regression of daily score change on that day's uploads, likes received, promotions,
comments and contest entries recovers the point values. Site: a short "how points seem
to work" table with fit quality, labelled as inferred.

## 11. Reconstructed history

So the site is not empty on day one, the first snapshot is used to rebuild what can be
rebuilt:

| Series | Source | Caveat shown on the chart |
|--------|--------|---------------------------|
| Public uploads per month since 2018, by size and category | `Date` of every artwork still listed | deleted artworks are missing, more so for older months |
| Sign-ups per month | id-to-date mapping from first uploads, times the measured share of ids in use | approximate before launch |
| Recommend picks per month | Recommend feed | promoted artworks later removed are missing |
| Cumulative likes and views by upload cohort | current counters | totals to date, not flows |
| Automated-like share by upload year | like lists sampled per year, as in the October study | sampled |

Reconstructed and measured periods are drawn differently, with the launch date marked.

## 12. Personal benchmarks

The statistics publish `data/benchmarks.json`: percentiles (10, 25, 50, 75, 90, 99) of
likes from people, raw likes and views, by canvas size, curation tier, photo or not,
and age band. The Download tool, where a user is already logged in to their own
account in the browser, reads that file and shows where each of their artworks falls.
Everything is computed in the browser; the user's data goes nowhere. This is a change
in `servoom/docs/src`, listed in `05-servoom-umbrella.md`.

## Effect on the jobs

| Job | Before | Now | What was added |
|-----|-------:|----:|----------------|
| Pulse, per hour | about 450 | about 545 | id walk (50), Popular pages (40), deeper like-list paging |
| Refresh, per 4 hours | about 440 | about 440 | nothing |
| Snapshot, per day | about 65,000 | about 66,200 | file downloads (350), vanished and unlisted follow-ups (450), calendar (10), deeper like lists (up to 300) |
| **Per day** | **about 78,000** | **about 82,000** | |

Run time: the pulse stays near 2 minutes of polling. The snapshot gains about 5 minutes
for downloads, decoding and hashing.

## Effect on storage (`servoom-raw`)

```
obs/like_events/YYYY/MM/DD.parquet     gallery_id, liker_id, observed_at, window_start
obs/artwork_meta/YYYY/MM/DD.parquet    tags, mentions, original id, language codes
obs/files/YYYY/MM/DD.parquet           per-file features and hashes
obs/uploads_all/YYYY/MM/DD.parquet     id walk: every upload with its flags
obs/popular/YYYY/MM/DD.parquet         list, rank, gallery_id, observed_at
obs/calendar.csv                       dated events
dim/accounts.parquet  (state branch)   one row per account seen
dim/hashes.parquet    (state branch)   all file hashes, for duplicate matching
```

About 1 MB more per day, so roughly 1.5 GB a year in total. The yearly move of old
months to a release asset, already planned, becomes a requirement.

## Effect on privacy

The private repository now holds histories of individual accounts: what each one liked
and when, whom uploads mention, which tags a person uses. That is more sensitive than
counters.

* Nothing from these tables is published except aggregates, under the existing rule
  that only top artists are ever named.
* Any published cell built from accounts (countries, tags, funnels) needs at least 5
  accounts.
* The salt for comment hashes lives in `servoom-raw`, not in the public repository.
* The deploy key is the one credential that guards all of it. It is used only by the
  steps that clone and push `servoom-raw`, and rotating it is a documented two-minute
  task.
* Raw rows older than 24 months are reduced to aggregates and deleted, unless a reason
  to keep them is recorded.

## Verified on 2026-10-04

1. `Cloud/GalleryInfo` does answer for other accounts' private uploads; item 6 handles
   them as counts only.
2. About 350 file downloads a day is fine, on the owner's experience of larger daily
   volumes.
3. The shop, store, advert and lottery listings answer without a device; the discount
   listing is empty and `GetNewAppVersion` is not usable yet (item 8).
