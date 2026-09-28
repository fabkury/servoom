# Questions and answers

## Round 1 (rejected by the user)

A first round asked which endpoint was meant, since no endpoint named "random" exists.
The user interrupted it and asked instead to check whether "random" is a *sort order* of
some listing endpoint (e.g. "give me 1 artwork from gallery X in random order").

Findings from that check (test account, 2 s between calls, every case called twice):

* `GetCategoryFileListV2`: `FileSort` 0..7 and `RefreshIndex` 0..3 on Classify 1 (Default)
  and 18 (Recommend) all return identical lists on repeat. `FileSort >= 1` behaves as
  "most liked" on Default; on Recommend, `FileSort >= 2` behaves as 0. `RefreshIndex`
  deterministically pages the Recommend feed back in time.
* `GetSomeoneListV2` (`FileSort` 0, 2), `Tag/GetTagGalleryListV3`, `SearchGalleryV3`,
  `Cloud/GetExpertGallery`, `Discover/GetAlbumListV2`, `GetHotFilesV2`, `Hot/GetHotFiles32`,
  `Device/GetHotList`, `Discover/GetTheme`, `DiscoverBanner`, `GetGalleryAdvert`,
  `Discover/GetTopNew`, `PhotoFrame/GetList`, `Discover/GetStoreList`: identical on repeat.
* 22 guessed names (`Cloud/GetRandomGallery`, `GetRandomFile`, `Discover/GetRandom`, ...)
  all answer `ReturnCode 10 "Command is not match"`, with or without a token.
* Only two endpoints vary from call to call: `/Cloud/GetHotTag` (5 tags per call) and
  `/Cloud/GetHotExpert` (featured artists; first entry fixed, the rest vary).

## Round 2

**Q: What should the study target?**
Options offered: `/Cloud/GetHotTag`; `/Cloud/GetHotExpert`; both; halt.
**A:** Both, and make it a total of 30 minutes instead of an hour.

**Q: What request rate is acceptable?**
Options offered: 1 per 3 s; 1 per 5 s; 1 per 10 s.
**A:** One request per second is probably ok.

**Q: Which account should make the requests?**
Options offered: test account `test_01`; main account.
**A:** Test account `test_01`.

## Resulting plan

30 minutes of sampling at one request per second, alternating the two endpoints
(about 900 calls each), logged in as the throwaway test account. Every raw response
is kept in `samples.jsonl`; the analysis estimates pool size (capture-recapture and
frequency-of-frequencies), per-item frequencies against a uniform hypothesis,
within-call structure (duplicates, ordering, `TagType` mix) and latency.
