# Divoom cloud: gallery, user, tag, discovery and profile endpoints

Read-only map of the Divoom cloud API behind the app's **Gallery**, **Discover**, user
profile and playlist screens. It complements [`FORUM_API.md`](FORUM_API.md) (forum,
comments, notification inbox) and [`FILE_FORMATS.md`](FILE_FORMATS.md) (the artwork
containers themselves).

How it was built: the endpoint names, request fields and response models come from the
HTTP layer of the Android app (version 3.8.40), read with a decompiler; every endpoint
listed as *verified* was then exercised on 2026-09-29 against `appin.divoom-gz.com` with a
throwaway account, and the field lists below are what the server actually returned. No
decompiled code is reproduced here or in servoom; the client is written from scratch.
Everything read-only that answered is wired into `DivoomClient`
(`python/servoom/client.py`); write-side, device-bound, commerce and moderation commands
are only listed.

## Conventions

* One JSON `POST` per command: `https://<host>/<Command>`, body `application/json`.
  The app adds `Connection: close` and sends no signature, API key or custom header.
* Base fields the app puts in **every** body: `Token`, `UserId` (from `/UserLogin`),
  `Command` (the path again) and `DeviceId` (the connected device, `0` without one).
  `Command` and `DeviceId` are optional for everything documented here.
* Listings page with 1-based inclusive `StartNum`/`EndNum`. **Each endpoint caps a page**
  (see the table below); a window larger than the cap is silently truncated to the first
  *cap* items after `StartNum`, so the next request must start at `StartNum + received`,
  not at `EndNum + 1`. `servoom.http.paginate` does that.
* Return codes: `0` ok; `1` "Failed" (also used for "no data"); `3` "Request data is
  incomplete" (a required field is missing, or the command needs a bound device);
  `10` unknown command; `11` login required / token mismatch; `12` "Request data is null".
* Ids arrive as strings in some records (`"ExpertUserId": "400343116"`,
  `"RegionId": "86"`) and as ints in others; requests accept ints everywhere.
* `Version` and `RefreshIndex` are sent by the app on gallery listings. `RefreshIndex` is
  ignored. `Version` is **not**: it is the client level the server filters artworks by, and
  a value below 18 silently hides newer artworks (see "The `Version` field").

### Hosts

| Host | Who uses it | Notes |
|------|-------------|-------|
| `app.divoom-gz.com` | web front-end (`pixel.divoom-gz.com`) and servoom | same data as `appin` |
| `appin.divoom-gz.com` | the app outside China (`fin.divoom-gz.com` for files) | reference host for this document |
| `appusa.divoom-gz.com` | the app's upload host outside China | serves listings too, but with `FileListNum` capped at 1000 and an `expire` flag: a cache |
| `appchina.divoom-gz.com` | the app in China (`fchina.divoom-gz.com` for files) | rejects tokens issued by `appin` (`ReturnCode 11`) |
| `apptest.divoom-gz.com` | Divoom's test build | same rejection |
| `f.divoom-gz.com` | file downloads (`https://f.divoom-gz.com/<FileId>`) | identical bytes from `fin.divoom-gz.com` |

### Anonymous access

Many read endpoints answer **without any token** (the web gallery relies on this). Verified
on 2026-09-29, requests sent with no `Token`/`UserId` at all:

| Works anonymously | Needs a token (`ReturnCode 11`) |
|-------------------|---------------------------------|
| `GetCategoryFileListV2`, `GetSomeoneListV2`/`V3`, `SearchGalleryV3`, `Discover/GetAlbumImageListV3`, `Cloud/GetExpertGallery` | `Tag/GetTagGalleryListV3`, `Playlist/GetSomeOneImageList`, `GetMyUploadListV3`, `GetMyLikeListV3` |
| `Comment/GetCommentListV3`, `GetCommentListV2`, `Cloud/GetFileData` | `Cloud/GalleryInfo`, `Cloud/GetLikeUserList` |
| `GetSomeoneInfoV2`, `GetExpertListV4`, `Cloud/GetHotExpert`, `Medal/GetList`, `Medal/GetNewValidList`, `LookScore` | `Tag/GetTagInfo`, `Tag/GetUserList`, `Tag/SearchTagSimple`, `Cloud/GetHotTag`, `Playlist/GetSomeOneList` |
| `Discover/GetAlbumListV3`, `Discover/GetAlbumInfo`, `Cloud/GetMatchInfo`, `Forum/GetList`, `Tag/SearchTagMoreV2` | `Discover/GetAlbumList`, `Discover/GetTheme`, `Discover/GetTopNew`, everything under `Lottery/`, `Mall/`, `Discount/`, `APP/GetServerUTC` |

`DivoomClient(anonymous=True)` skips credentials and sends no auth fields; it logs a
warning when a method known to need a token is called that way.

**Anonymous listings stop after 1,230 items.** Without a token, `GetCategoryFileListV2`
serves only the first 1,230 items (41 pages of 30) of any `Classify`, whatever the filters.
Later windows answer `ReturnCode 0` with an empty list, which looks exactly like the real
end of the listing. With a token the same listings page to the end (totals in the
`Classify` table below), so categories smaller than the cap (10, 13, 23–36) are
complete anonymously, while the largest show as little as 0.3% of their items (Default).
Categories 21 and 38 answer empty without a token. Files are not gated:
`https://f.divoom-gz.com/<FileId>` needs no token, so the cap limits which `FileId`s an
anonymous caller can learn, not what it can download. Measured on 2026-10-03 for every id
in 0..40, with `Version 12` on 2026-10-03 and again with `Version 19` the same day; the other listings (`GetSomeoneListV3`, `SearchGalleryV3`, ...) were not checked
for a cap.

### Page caps

| Cap | Endpoints |
|----:|-----------|
| 30 | `GetCategoryFileListV2`, `GetExpertListV4`, `Tag/GetUserList`, `Discover/GetAlbumListV3`, `Tag/GetTagGalleryListV3` (29 seen) |
| 100 | `GetSomeoneListV3`, `SearchGalleryV3`, `Discover/GetAlbumImageListV3`, `Comment/GetCommentListV3`, `Cloud/GetLikeUserList`, `Forum/GetList` |
| none seen | `Medal/GetList` (118 in one answer), `Cloud/GetExpertGallery` (returned 102 for a window of 100) |

`FileListNum` is not a real total: it is `10000` on most listings and `1000` on cached
ones. Rely on an empty page instead. With `FileSort=1` (popular) the order drifts between
calls, so two adjacent windows fetched seconds apart can overlap by an item or two.

## Gallery filters

Every artwork listing takes the same filter block (`GetCloudBaseRequestV2` in the app):

| Field | Values | Notes |
|-------|--------|-------|
| `FileSort` | `0` latest upload, `1` popular (`2` behaves like `1`) | `servoom.const.GallerySort` |
| `FileSize` | bitmask: `1` 16x16, `2` 32x32, `4` 64x64, `16` 128x128, `32` 256x256, `64` 256 circular; `127` all | bit `8` is unused by the filter UI; the Planet lamp category reports `FileSize 8` on its items | `servoom.const.GallerySize` |
| `FileType` | `0` picture, `1` animation, `2` multi-picture, `3` multi-animation, `4` LED text, `5` all, `6` sand | `9` appears on Planet items (`FileType` filter cannot select it); see `FILE_FORMATS.md` |
| `Classify` | category id, table below | `servoom.const.GalleryCategory` |
| `StartNum`, `EndNum` | paging | cap 30 or 100 |
| `Version` | client level, send `19` | below 18 the server hides newer artworks, see "The `Version` field" |
| `RefreshIndex` | ignored | the app sends `0` |

### The `Version` field

`Version` tells the server which app generation is asking, and the server leaves out every
artwork that needs a newer one. Each artwork has a minimum level; a listing returns only
the artworks whose level is at or below the `Version` sent, with `ReturnCode 0` and no
sign that anything was withheld. The levels are nested (an artwork visible at one value
is visible at every higher one). **Send 19**, as the current app does; 18 through 1000
answered identically, and a string (`"19"`) works like the number.

Measured on 2026-10-03 on the Recommend feed (`Classify 18`), every `Version` from 1 to
19 over the 1,058 artworks uploaded in the previous 60 days:

| `Version` | Share of the feed returned | What this level adds |
|----------:|---------------------------:|----------------------|
| absent, 0, negative, 1–4 | 0% | nothing recent: 1–3 page through 2018 items only, absent, 0 and negative give a shorter list still |
| 5–8 | 12% | 16x16, 32x32 and some 64x64 artworks without a layer file |
| 9–11 | 14% | more 64x64 artworks without a layer file |
| 12 | 45% | artworks with `CopyrightFlag 1`, at any canvas size |
| 13–14 | 85% | artworks with a layer file (`LayerFileId`), up to 64x64 |
| 15–17 | 95% | 128x128 |
| 18 and up | 100% | 256x256 |

The right-hand column describes what each level mostly contains, not an exact rule: the
level is not derivable from the record's fields. `CopyrightFlag 1` puts an artwork at
level 12 whatever its size or layer file in 315 of 338 cases, a few 64x64 artworks sit at
5 and others at 9 with no visible difference, and the container format does not decide it
(format 26 files appear at every level from 5 to 15). Over the whole feed, `Version 12`
returns 29,963 of 41,307 items, and only 46% of the artworks uploaded since February 2026.

Other listings, compared at `Version` absent, 1, 5, 12, 13, 19 and 99:

| Listing | Effect of `Version` |
|---------|---------------------|
| `GetCategoryFileListV2`, `Tag/GetTagGalleryListV3`, `Discover/GetAlbumImageListV3` | the ladder above |
| `GetSomeoneListV3` | empty below 12; 12 and 13 return a slightly different set from 19 and 99 |
| `SearchGalleryV3` | fewer results when absent (6) or 1 (39); a different set at 5; identical from 12 up for the query tried |
| `Discover/GetAlbumListV3`, `GetExpertListV4`, `Cloud/GetExpertGallery` | none |
| `GetMyLikeListV3`, `Playlist/GetSomeOneImageList` | not measured (the test account's lists were empty) |

`Classify` ids and the names the app shows (an id not in the app's tab list still filters,
the rows marked *hidden* were found by sweeping 0..40). *Items* is how far a logged-in
client could page on 2026-10-03 with `FileSize 127`, `FileType 5`, `FileSort 0`,
`Version 19`; a narrower `FileSize` gives a different count (Recommend: 16,357 at 16x16,
7,124 at 32x32, 12,860 at 64x64, 4,099 at 128x128, 865 at 256x256), and so does a lower
`Version` (Recommend: 29,963 with `Version 12`). Anonymous callers see at most 1,230 of
them (see "Anonymous access").

| Id | App tab | Items | Id | App tab | Items |
|---:|---------|------:|---:|---------|------:|
| 0 | NEW (curated: every item has `IsAddNew 1`) | 184,147 | 17 | Season | 32,155 |
| 1 | Default | 447,003 | 18 | Recommend | 41,307 |
| 2 | hidden: LED text (`FileType 4`) | 68,919 | 19 | Planet (28-LED lamp artworks, `FileType 9`, `FileSize 8`) | 19,393 |
| 3 | Character | 127,005 | 20 | Follow (uploads of followed users; needs a token) | per account |
| 4 | Emoji | 66,200 | 21 | hidden: **held uploads awaiting photo review** (see below) | 35, token only |
| 5 | Daily | 27,970 | 22 | hidden: 12 same-day uploads with a token on 2026-10-03 (`ReturnCode 3` on 2026-09-29), not identified | 12 |
| 6 | Nature | 137,693 | 23–28 | hidden: legacy/event buckets (Signboard 2020, Halloween, ...) | 93–167 each |
| 7 | Icon | 53,041 | 29 | Pixel Coloring (fill game) | 226 |
| 8 | Pattern | 94,754 | 30 | Pixel Match (current event, see `Cloud/GetMatchInfo`) | 301 |
| 9 | Creative | 49,459 | 31 | Plant | 18 |
| 10 | hidden: old bucket, still populated | 283 | 32 | Animal | 82 |
| 11 | hidden: old bucket, still populated | 13,557 | 33 | Human | 30 |
| 12 | Photo | 381,395 | 34 | Emoji (second bucket) | 19 |
| 13 | hidden: old bucket, still populated | 101 | 35 | Food | 23 |
| 14 | hidden: same feed as 0 | 193,888 | 36 | Others | 44 |
| 15 | Gadget | 18,368 | 37, 39 | moderator queues; 37 empty, 39 held 2 same-day uploads on 2026-10-03 | 0, 2 |
| 16 | Business | 3,177 | 38 | hidden: unidentified queue, served to any logged-in account | 46,849, token only |
| | | | 40 | AI | 7,950 |
| | | | 254 | reported images (moderator) | |
| | | | 255 | one placeholder record | |

### Category 21: the review queue

`Classify 21` is not a category people upload to. It lists uploads that are **held for
review**: every record carries `CheckConfirm 1` and `HideFlag 1`, zero likes, comments
and views, and shows up nowhere else (not in the NEW feed, not in the uploader's public
profile, not in the Photo category). Observed on 2026-09-29: four 64x64 photo-like
images, waiting between half an hour and over an hour, unchanged across 50 minutes of
polling; approved items appear later in `Classify 12` (Photo) with `CheckConfirm 2`, and
items that stay pending end up hidden under their uploader's profile listing with
`CheckConfirm 1` weeks later. The listing is silently token-gated: without a token it
answers `ReturnCode 0` and an empty list; any logged-in account sees it, moderator rights
are not needed. `DivoomClient` drops `HideFlag 1` records by default, so read it with
`Settings(respect_hide_flag=False)`. Some `CheckConfirm 1` photos are public
(`HideFlag 0`, with views); what decides which pending uploads are held is not visible.

## The artwork record

Every artwork listing (`FileList` items) carries the same record; `Cloud/GalleryInfo`
returns the same fields for one id. Verified field list:

| Field | Meaning |
|-------|---------|
| `GalleryId`, `FileId`, `FileName` | id, download path (`https://f.divoom-gz.com/<FileId>`), title |
| `FileType`, `FileSize`, `Classify` | see the filter table |
| `UserId`, `UserName`, `UserHeaderId`, `Level`, `RegionId`, `CountryISOCode`, `PixelAmbId`, `PixelAmbName` | uploader; `PixelAmb*` is the ambassador badge image/name, empty for most users |
| `Date`, `LikeUTC`, `CommentUTC` | upload time and the last like/comment (unix seconds) |
| `LikeCnt`, `CommentCnt`, `ShareCnt`, `WatchCnt` | counters |
| `IsLike`, `IsFollow` | the caller's relation (always 0 anonymously) |
| `Content`, `FileTagArray`, `AtList` | caption, `#tags`, `@mentions` (`{AtUserId, AtNickName}`) |
| `PrivateFlag`, `HideFlag`, `IsDel`, `CheckConfirm`, `CopyrightFlag`, `AIFlag` | visibility/moderation flags. `CheckConfirm` is the **photo-review** status: `0` on ordinary pixel art (every record of the NEW feed), `1` pending, `2` approved, `3` the other verdict (still listed in the Photo category) |
| `IsAddNew`, `IsAddRecommend`, `GoodLevel` | curation: promoted to NEW / Recommend |
| `LayerFileId`, `MusicFileId`, `OriginalGalleryId` | layer-file companion (`FILE_FORMATS.md`), attached music, source of a remix |
| `FillGameScore`, `FillGameIsFinish` | Pixel Coloring game state |
| `ReportInfo`, `ReportUser`, `itemId`, `itemType` | present in the app model, not seen populated |

## Gallery listings

All verified, all take the filter block above and page with `StartNum`/`EndNum`. Response:
`FileList`, `CurListNum`, `FileListNum`.

| Command | Extra request fields | Client method | Auth |
|---------|----------------------|---------------|------|
| `GetCategoryFileListV2` | `Classify` | `fetch_category_files(category_id)` | no |
| `GetSomeoneListV3` (the app's current call; `V2` answers identically) | `SomeOneUserId`, `ShowAllFlag` (managers only) | `fetch_someone_arts(user_id)` | no |
| `SearchGalleryV3` | `Keywords`, `KeywordsEn`; **send the filter block**: with `Keywords` alone the server applies a narrow default and returns a handful of items | `search_gallery(query)` | no |
| `Tag/GetTagGalleryListV3` | `TagName`, `Mode` (0/1/2, no visible effect) | `fetch_tag_gallery(tag)` | yes |
| `GetMyUploadListV3` | — | `fetch_my_arts()` | yes |
| `GetMyLikeListV3` | — | `fetch_my_likes()` | yes |
| `Discover/GetAlbumImageListV3` | `AlbumId` | `fetch_album_arts(album_id)` | no |
| `Playlist/GetSomeOneImageList` | `TargetUserId`, `PlayId` | `fetch_playlist_arts(user_id, play_id)` | yes |
| `Playlist/GetMyImageList` | `PlayId` | `fetch_playlist_arts(None, play_id)` | yes |
| `Cloud/GetExpertGallery` | only paging | `fetch_expert_gallery()` | no |

`Cloud/GetExpertGallery` is the "top artists' picks" feed (ambassador-level uploaders,
`PixelAmbName` set); the app no longer calls it but the server still serves it.

## One artwork

* `Cloud/GalleryInfo` — request `GalleryId`; the artwork record plus `IsNewComment`,
  `WatchCnt`, `OriginalFileId`. Token required. `fetch_artwork_info`.
* `Cloud/GetLikeUserList` — `GalleryId` + paging; `UserList` of
  `{UserId, NickName, HeadId, Level, Score, FansCnt, RegionId, CountryISOCode, PixelAmbId, PixelAmbName, IsFollow}`.
  Token required. `fetch_likes_for_art`.
* `Comment/GetCommentListV3` — `GalleryId`, `MessageId` (0), `Language` + paging;
  `CommentList` of threaded comments (`CommentChildList`, `AtList`, `AuthorLike`,
  `LikeCnt`, `Relation`, `Level`) plus `CommentListNum` (the real total) and
  `LikeListInfo`. Anonymous. `fetch_comments_for_art`.
* `GetCommentListV2` — flat list with `ParentCommentId`; superseded by V3.
* `Cloud/GetFileData` — `GalleryId` **or** `FileId`; no token. The web gallery's helper: the
  server decodes the artwork and returns `FileData` (a list of RGB bytes, `768` per frame),
  `PicCount`, `Speed`, `xScreenCount`, `yScreenCount`, `FileName`. It only understands the
  legacy 16x16 containers (formats 8/9 and the old 64x64 animations, which it downsamples
  to 16x16); modern multi-panel formats come back with `PicCount 1` and an empty
  `FileData`. `fetch_legacy_preview`.

## Users

| Command | Request | Response | Client method | Auth |
|---------|---------|----------|---------------|------|
| `GetSomeoneInfoV2` | `SomeOneUserId`, `Language` | `NickName`, `HeadId`, `BackgroundId`, `UserNewSign`, `Level`, `Score`, `LikeCnt`, `FansCnt`, `FollowCnt`, `MedalList[{ImageId}]`, `PixelAmb*`, `PixelFlag`, `RegionId`, `CountryISOCode`, `Relation`, `IsFollow`, `BlackFlag`, `MessageFlag`, `WebUrl` (the public web profile) | `fetch_someone_info` | no |
| `LookScore` | `TargetUserId` | `Score`, `PixelCnt`, `AniCnt`, `RecommendCnt`, `TopCnt` | `fetch_user_score` | no |
| `Medal/GetList` | `TargetUserId`, `Langue` | `MedalList[{MedalId, Name, SubTitle, Explain, IsValid, ValidTime, ActionType, StarTime, EndTime, ValidImageId, InValidImageId}]`, `MedalValidCnt` | `fetch_user_medals` | no |
| `GetExpertListV4` | paging, `Language` | `ExpertList[{UserId, NickName, HeadId, Level, Score, FansCnt, MissionScore, PixelAmb*, RegionId, CountryISOCode, IsFollow, MedalList, FileList[5 sample artworks]}]`, `ExpertListNum` | `fetch_experts` | no |
| `Cloud/GetHotExpert` | — (optional `RegionId`) | `ExpertList[10 × {ExpertUserId, NickName, ExpertHeadFileID, Level, CountryISOCode, PixelAmb*}]` | `fetch_hot_experts` | no |
| `Tag/GetUserList` | `TagName`, `Language`, paging | `UserList` (same user record as `GetLikeUserList`) | `fetch_tag_users` | yes |
| `GetUserAllInfo` | `Language` | the current account: `Email`, `Nickname`, `HeadId`, `RegionId`, `CountryISOCode`, `Level`, `MissionScore`, `ManagerFlag`, `VendorFlag`, buddy fields, `TimeStamp` | `fetch_my_info` | yes |
| `GetFansListV2`, `GetFollowListV2` | paging, `Language` | `FollowList` (user records), `FollowListNum` — **own account only**: `SomeOneUserId`/`TargetUserId` are accepted and ignored | `fetch_my_followers`, `fetch_my_following` | yes |
| `User/GetBlackList` | paging | `BlackList[{UserId}]` | `fetch_blacklist` | yes |
| `SearchUser` | `Keywords` | `ReturnCode 1` for every query (server-side breakage, unchanged since the earlier survey) | `search_user` | — |
| `Playlist/GetSomeOneList` | `TargetUserId`, paging | `PlayList[{PlayId, Name, Describe, CoverFileId, Count, HideFlag, AddFlag}]` | `fetch_user_playlists` | yes |
| `Playlist/GetMyList` | paging | same | `fetch_my_playlists` | yes |

`User/GetPersonalInfo` (the GDPR self-export summary) answers with a PHP notice instead
of JSON whatever is sent; `User/GetPersonalInfoCnt`, `User/GetBindInfo`,
`User/GetKidsMode` work but only describe the caller's own account settings.

## Tags

| Command | Request | Response | Client method | Auth |
|---------|---------|----------|---------------|------|
| `Tag/GetTagInfo` | `TagName` | `GalleryCnt`, `FollowCnt`, `UserCnt`, `IsFollow`, `UserList[4 × {UserId, HeadId}]` | `fetch_tag_info` | yes |
| `Tag/SearchTagSimple` | `TagKey` | `TagList[≤30 × {TagName, GalleryCnt}]`, prefix matches | `suggest_tags` | yes |
| `Tag/SearchTagMoreV2` | `Keywords` (fuzzy) **or** `TagKey` (prefix; wins when both are sent), paging (required), `FileSize`, `FileSort` | `TagList[{TagName, GalleryCnt, FollowCnt, IsFollow, GalleryList[5 × {GalleryId, FileId, LikeCnt, CommentCnt, IsLike}]}]` | `search_tag` | no |
| `Cloud/GetHotTag` | `Language` | `TagList[5 × {TagName, TagType}]` | `fetch_hot_tags` | yes |

## Discovery

| Command | Request | Response | Client method | Auth |
|---------|---------|----------|---------------|------|
| `Discover/GetAlbumListV3` | paging, `FileSize`, `FileSort` | `AlbumList[{AlbumId, AlbumName, AlbumImageId, AlbumBigImageId, LikeCnt, GalleryCnt, GalleryList[5 samples]}]` | `fetch_albums` | no |
| `Discover/GetAlbumList` | `CountryISOCode`, `Langue` | all albums (46) without counters | — | yes |
| `Discover/GetAlbumInfo` | `AlbumId`, `CountryISOCode`, `Langue` | `LikeCnt`, `CommentCnt`, `ShareCnt`, `ForumId`, `KeyWork` | `fetch_album_info` | no |
| `Discover/GetTheme` | — | `ThemeList[{ForumId, ImageId, Title}]`: the Discover carousel (contest themes) | `fetch_discover_themes` | yes |
| `Discover/GetTopNew` | — | `NewList[2 × {ForumId, Title}]`, `NewImageId`, `TextColor` | `fetch_discover_top_new` | yes |
| `Cloud/GetMatchInfo` | — | `MatchKey`: the running contest (`"Monster2026"` on 2026-09-29), the tag `Classify 30` filters on | `fetch_match_info` | no |
| `Discover/GetStoreList`, `GetStoreV2`, `Discover/GetRadioList` | — | product links, shop banners, radio presets | — | mixed |

Albums are curated collections; their comment thread lives on the forum post `ForumId`.

### The two random samplers

Nothing in the API draws artworks at random: 22 guessed paths answer `ReturnCode 10`, and
every listing (all `FileSort` and `RefreshIndex` values included) returns byte-identical
lists on repeat. Only `Cloud/GetHotTag` and `Cloud/GetHotExpert` vary between calls, and
each is a uniform random subset of a small fixed list, returned in the list's own order
with no memory between calls: 5 of 24 curated tags (stale seasonal content, token
required) and 10 of 25 curated artists (no token). Measured on 2026-09-28 over 1801
requests; the study (`requests/01-divoom-random-artwork-endpoint-stats/`, retired) is in
the git history up to commit `5a4b4e2`.

## Inbox extras (beyond `FORUM_API.md`)

* `Message/GetConversationList` — private chats of the caller:
  `ConversationList[{TargetUserId, Message, SendTime}]`. `fetch_conversations`.
* `GetNewLetterListV2` — system letters: `LetterList`, `LastIndex`. `fetch_letters`.

## Not reachable without a device

Every `Channel/*`, `Sys/*`, `Alarm/*`, `Photo/*`, `Tools/*`, `TimePlan/*`, `Tomato/*`,
`Voice/*`, `Led/*`, `Vision/*`, `AidSleep/*`, `Danmaku/*` command (about 260 of the 563
the app knows) is device configuration; the server answers `ReturnCode 3` unless the body
names a `DeviceId` bound to the account. That includes the **clock store** listings
(`Channel/StoreClockGetClassify`, `Channel/StoreClockGetList`, `Channel/StoreGetBanner`,
`Channel/StoreGetTopicList`, `Channel/GetClockCommentList`), which would otherwise be
community content. They are documented here so nobody re-probes them; a bound device is
the only way in.

## Listed only

* **Marketing / commerce** (verified, not wired): `GetGalleryAdvert`, `GetStartLogo`,
  `GetNewAppVersion`, `APP/GetServerUTC`, `Lottery/{Announce,GetPrizeInfo,GetLotteryCnt,MyList}`,
  `Mall/GetListV2`, `Discount/{GetMyList,GetNewDiscount}`, `Shop/GetShopAuthLink`,
  `Cloud/DownloadApp`.
* **Moderation** (`Manager/*`, 22 commands: report queues, pass/limit/ban): answer
  `ReturnCode 1` for a normal account; `Manager/GetReportGallery` lists reported artworks.
* **Web-only legacy gallery**: `Cloud/GetCategoryDataList` and `Cloud/GetSomeoneDataList`
  (payload `FileType 101`, `Version 7`) return the pre-2019 16x16 gallery (`GalleryId`
  below 20000) with the pixels inline (`FileData`, `PicCount`, `Speed`); `FileSize` is
  ignored. Only the web front-end uses them.
* **Write side** (never called by servoom): `GalleryLikeV2`, `CommentLikeV2`,
  `FollowExpertV2`, `Tag/Follow`, `HideGalleryV2`, `DeleteGalleryV2`, `Cloud/SetGalleryPrivate`,
  `Cloud/SetGalleryCopyright`, `Cloud/ReportUser`, `ReportGalleryV2`, `ReportCommentV2`,
  `Cloud/GalleryUploadV3`, `Cloud/GalleryAsyncUploadV3`, `Cloud/UploadPicture`,
  `Cloud/WeakWatchGallery`, `AddDownloads`, `ReduceDownloads`, `AddWatch`, `Playlist/{NewList,Rename,SetDescribe,SetCover,DeleteList,Hide,AddImageToList,RemoveImage,SendDevice}`,
  `User/{BlackList,SetUserHeadV3,SetUserNewSign,SetBackgroundImageV2,SetKidsMode,DeleteUser,...}`,
  `SetUserInfo`, `ChangPassword`, `UserRegister`, `UserLogout`, `App/DelUser`, `AI/*`,
  `EveryDayMission`, `MissionShare`, `Lottery/Start`, `Mall/Buy`.

## Using it

```python
from servoom import DivoomClient
from servoom.const import GalleryCategory, GallerySize, GallerySort

c = DivoomClient(anonymous=True)                      # no credentials needed for these
for art in c.fetch_category_files(GalleryCategory.ANIMAL, limit=90,
                                  FileSort=GallerySort.POPULAR, FileSize=GallerySize.W64):
    print(art["GalleryId"], art["FileName"], art["LikeCnt"])
experts = c.fetch_experts(limit=30)                   # each with 5 sample artworks
albums = c.fetch_albums()                             # curated collections
arts = c.fetch_album_arts(albums[0]["AlbumId"], limit=100)
medals = c.fetch_user_medals(400343116)

c = DivoomClient(); c.login()                         # token-only endpoints
info = c.fetch_tag_info("cat")
users = c.fetch_tag_users("cat", limit=60)
mine = c.fetch_my_likes()
```
