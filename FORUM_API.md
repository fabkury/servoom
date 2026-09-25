# Divoom cloud: forum, comments and notification endpoints

Reverse-engineered, read-only map of the endpoints behind the app's **Forum** tab (the
official article feed: contests, news, "Behind the Pixels" interviews, product posts) plus
the related comment and notification endpoints. Probed on 2026-09-24 against
`https://app.divoom-gz.com` with a throwaway account; everything here is wired into
`DivoomClient` (`python/servoom/client.py`) unless marked otherwise. The undocumented
endpoint list at <https://divoom.2a03.party/api/app.html> was the starting point.

## Conventions

* JSON `POST` with `Content-Type: application/json`; every call carries `Token` and
  `UserId` from `/UserLogin`.
* Listings page with 1-based inclusive `StartNum`/`EndNum`. Windows of 100 (posts) and
  400 (comments) were served in full, so page size is generous. Past the end the server
  answers `ReturnCode 3` ("Request data is incomplete") rather than an empty list.
* Return codes seen: `0` ok, `1` "Failed", `3` incomplete request, `10` "Command is not
  match" (unknown path; the body also carries `"Name": "IndexDefaultMethod"`), `12`
  "Request data is null" (a required id is missing).
* Ids come back as **strings** in list records (`"ForumId": "3440"`) but are accepted as
  ints in requests.

## Two feeds, selected by `RegionId`

The server keeps two separate article feeds. `RegionId` in the request picks one:

| `RegionId`             | Feed                        | Size on 2026-09-24 |
|------------------------|-----------------------------|--------------------|
| `86`                   | Chinese (titles in Chinese) | 452 posts          |
| anything else, incl. 0 | International (English)     | 871 posts          |
| omitted                | the account's own region; API-registered accounts carry `RegionId 0` in `GetUserAllInfo` and then get the **Chinese** feed | |

`CountryISOCode`, `Language` and `TimeZone` (on login or per request) do not change the
feed. `servoom.const.ForumRegion` holds the two values. Post ids are disjoint between the
feeds even when the content is a translation (Summer Quest 2026 winners: `3438` CN, `3440`
EN).

## `/Forum/GetTag`

Request: auth (+ optional `RegionId`). Response `TagList`:

```json
[{"TagValue": "2", "TagName": "Contest"}, {"TagValue": "4", "TagName": "News"},
 {"TagValue": "6", "TagName": "Skill Share"}, {"TagValue": "8", "TagName": "Reviews"}]
```

Same four tags on both feeds. Counts (international): Contest 185, News 258, Skill
Share 35, Reviews 408.

## `/Forum/GetList`

Request: auth, `StartNum`, `EndNum`, optional `RegionId`, optional `Tag` (a `TagValue`;
`TagID`/`TagId` are ignored).

Response: `HeaderNum` (string), `TotalNum` (int), `CurListNum` (int), `ForumList` (array).

* **Curated block.** Page 1 opens with a non-chronological block: `HeaderNum` pinned
  posts followed by featured ones (16 entries in total on both feeds while `HeaderNum`
  says 5). The chronological newest-first list starts after it and **repeats** those
  posts, so de-duplicate on `ForumId`. Later pages report `HeaderNum: 0`.
* `Tag` filters the chronological part only; the curated block is always returned.
* The tail is the oldest post (`ForumId 14`, 2019-07-01).

`ForumList` record (all posts are by the official account, `UserId 300000001` "Dida"):

| Field | Notes |
|-------|-------|
| `ForumId` | post id (string) |
| `TagID` | `TagValue` of the tag |
| `Title` | plain text |
| `Date` | unix seconds |
| `ImageId` | hero image path on `f.divoom-gz.com` |
| `LinkUrlNoComment`, `LinkUrlWithComment` | `http://m.divoom-gz.com/article.php?ArticleID=<ForumId>&Flag=0` (both identical in practice) |
| `UserId`, `NickName`, `HeadId`, `PixelAmbId`, `PixelAmbName`, `CountryISOCode`, `Level` | author |
| `LikeCnt`, `CommentCnt`, `WatchCnt` | counters (strings); `CommentCnt` includes replies |
| `IsFollow`, `IsLike` | current user's relation to the author / post |

### Article body

The article page is a mobile web view: the title, author, date, a stack of images, and for
most posts a single link ("Click here to check the article!") to a landing page on
`download.divoom.com`, e.g. `http://download.divoom.com/2026-Quest-win-en` (`-cn` on the
Chinese feed). There is no JSON endpoint for the body; fetch the `LinkUrlNoComment` page
and follow that link if you need the text.

## `/Forum/GetForumUrl`

Request: auth. Returns one record with the same fields as a `ForumList` entry (plus
`TagID`): always post `102` ("PIXEL ART AMBASSADOR PROGRAM", 2020-03-28), the article the
app links from the ambassador badge. Every id-like parameter tried (`ForumId`, `ForumID`,
`ArticleID`, `ArticleId`, `ID`, `Id`, with and without `RegionId`) is ignored, so there is
**no per-id post lookup**: filter `/Forum/GetList` by `ForumId` instead.

## `/Forum/GetCommentListV2`

Request: auth, `ForumId`, `StartNum`, `EndNum` (+ optional `RegionId`; not needed, the
id is global). Response: `CommentListNum` (string, **top-level + replies**), `CurListNum`
(top-level records in this page), `CommentList`.

Top-level comments come newest first; replies are embedded, newest first, under
`CommentChildList` (no separate sub-comment endpoint exists; `/Forum/GetSubCommentList`
and similar guesses return code 10). Comment record:

| Field | Notes |
|-------|-------|
| `CommentId` / `ID` | id (string, both present) |
| `ArticleID` | the `ForumId` |
| `UserId` / `UserID`, `NickName`, `HeadId`, `Level`, `RegionId`, `CountryISOCode`, `PixelAmbId`, `PixelAmbName` | author |
| `Content` / `Comment` | text (same value); `FilterContent` is empty |
| `CreateTime` | `"YYYY-MM-DD HH:MM:SS"` (server local time); `Date` is the unix version; `ModeTime` null |
| `LikeNum` / `LikeCnt` | likes (string) |
| `SubNum` | number of replies |
| `AckUserId`, `AckUserNickName` | the user a reply answers (`"0"`/`""` when replying to the thread) |
| `AtList` | `[{"AtUserId": "...", "AtNickName": "..."}]` for `@mentions` |
| `Status` | `"1"` |
| `IsLike`, `AuthorLike`, `Relation` | current-user / author flags |
| `CommentChildList` | replies, same shape (absent on replies) |

`/Forum/GetCommentList` (V1) takes the same request and returns a flat list with fewer
fields (`UserId`, `NickName`, `HeadId`, `Level`, `Comment`, `RegionId`, `CountryISOCode`,
`Date`, `IsLike`, `LikeCnt`, `CommentId`), replies mixed in. Prefer V2.

## `/Comment/GetCommentListV3` (gallery comments)

Request: auth, `GalleryId`, `StartNum`, `EndNum`. Response: `CommentListNum`,
`CurListNum`, `LikeListInfo`, `CommentList`. Same nested layout as the forum V2 list with
gallery naming (`CoId`, `ImgId`, `Time`, `IsRead`, `RobertFlag`, `AtListInfo`). The older
`/GetCommentListV2` returns a flat list with `ParentCommentId` and a bogus
`CommentListNum: 10000`.

## Notification inbox (`/Message/*`)

All take just auth (plus `StartNum`/`EndNum` for the lists).

| Path | Response |
|------|----------|
| `/Message/GetUnReadCnt` | `LikeUnReadCnt`, `CommentUnReadCnt`, `FansUnReadCnt` |
| `/Message/GetNotifyConfig` | `LikeConfig`, `CommentConfig`, `FansConfig` (`"1"` = on). `/Message/SetNotifyConfig` presumably writes them; not exercised |
| `/Message/GetLikeList` | `UnReadCnt`, `LikeList` (likes received) |
| `/Message/GetCommentList` | `UnReadCnt`, `LikeList` (yes, the key is `LikeList`; comments received) |
| `/Message/GetFansList` | `UnReadCnt`, `LikeList` (new followers) |

All three lists were empty on the fresh test account, so record shapes are unverified.

## Community chat rooms: `/MessageGroup/GetGroupList`

Request: auth. Response `ClassifyList[]` of `{ClassifyName, GroupList[]}`; groups have
`GroupId` (e.g. `"Chat"`, `"H3"` Gallery, `"AI"`, `"I2"` Feedback & Suggestion, language
rooms `"spanish"`, `"German"`, ...), `GroupName`, `ChannelId` (`"busChannel"`),
`GroupPixelFileId`, `GroupExplain` (rules text), `MessageType`, `TextInterval`,
`PixelInterval`, `PictureInterval`, `VideoInterval` (posting cooldowns in seconds), `Joined`.

Only this directory is served by the cloud API. The chat traffic goes through the IM
provider the app embeds (the login response's `UserToken` names `rongnav.com` /
`rongcfg.com` hosts, i.e. RongCloud), so the messages are not reachable with these JSON
calls; every `/MessageGroup/Get*` path guessed for history returned code 10.

## Related

* `/Discover/GetTopNew`: `NewList` of two featured `{ForumId, Title}` for the Discover
  banner plus `NewImageId`, `TextColor`. Returned Chinese-feed ids regardless of `RegionId`.
* `/GetUserAllInfo`: full profile of the current user, including `RegionId` and
  `CountryISOCode`.
* `/GetNewLetterListV2`: `LastIndex`, `LetterList` (private letters; empty on the test
  account).
* Write-side forum endpoints listed on the reference page but **not** exercised:
  `/Forum/Like`, `/Forum/CommentLike`, `/Forum/ReportComment`, `/Community/DeleteComment`,
  `/Community/ReportComment`, `/CommentLikeV2`, `/ReportCommentV2`.

## Using it

```python
from servoom import DivoomClient
from servoom.const import ForumRegion

c = DivoomClient(); c.login()
for post in c.fetch_forum_posts(limit=50):                 # international feed, newest first
    print(post["ForumId"], post["Title"], post["CommentCnt"])
comments = c.fetch_forum_comments(3440)                     # replies under CommentChildList
cn_posts = c.fetch_forum_posts(region=ForumRegion.CHINA, tag=6)   # Chinese "Skill Share"
```
