"""Preserved reverse-engineering findings for the Divoom cloud — reference material.

Nothing in this module is imported by the live code paths (client, decoders, CLI). It is
kept, documented and importable because it captures hard-won knowledge about the Divoom
gallery API that is useful for future work:

* the gallery **category / type / sorting / dimension** enumerations observed in the app,
* dict-to-attribute **mappers** for the raw ``GalleryInfo`` / ``AlbumInfo`` / ``UserInfo``
  JSON records, and
* a catalog of **experimental endpoints** that were probed while mapping the API (working,
  partially working, or unknown).

Treat these as notes-as-code: values may be stale and are not covered by tests. When you
wire one of these into ``servoom.client``, promote the relevant piece into a live module
(e.g. ``servoom.const``) and add a test.

Previously these lived as dead code in ``servoom/const.py`` and ``servoom/config.py``.
"""

from enum import Enum


# ---------------------------------------------------------------------------
# Gallery enumerations (observed in the Aurabox/Divoom app)
# ---------------------------------------------------------------------------
# ``Classify`` (category), ``FileSort`` and ``FileSize`` are live filters now; the app's
# own table (with the hidden ids that still filter) is in CLOUD_API.md.
from .const import GalleryCategory, GalleryFileType, GallerySize, GallerySort  # noqa: E402,F401

GallerySorting = GallerySort  # historical name


class GalleryType(int, Enum):
    PICTURE = 0
    ANIMATION = 1
    MULTI_PICTURE = 2
    MULTI_ANIMATION = 3
    LED = 4
    ALL = 5
    SAND = 6
    DESIGN_HEAD_DEVICE = 101
    DESIGN_IMPORT = 103
    DESIGN_CHANNEL_DEVICE = 104


class GalleryDimension(int, Enum):
    """Superseded by :class:`servoom.const.GallerySize` (same bits). Kept for the
    combined masks; bit 8 is what Planet-lamp records report as ``FileSize``."""

    W16H16 = 1
    W32H32 = 2
    W64H64 = 4
    UNDER128 = 15
    W128H128 = 16
    UNDER256 = 31
    W256H256 = 32


# ---------------------------------------------------------------------------
# Raw-record mappers
# ---------------------------------------------------------------------------
class BaseDictInfo(dict):
    """Read-only view that renames selected raw API keys to snake_case attributes while
    remaining JSON-serialisable (it *is* a ``dict``). Subclasses set ``_KEYS_MAP``."""

    _KEYS_MAP: dict = {}

    def __init__(self, info: dict):
        for src, dst in self._KEYS_MAP.items():
            self.__dict__[dst] = info.get(src)
        dict.__init__(self, **self.__dict__)

    def __setattr__(self, name, value):
        raise AttributeError(f"{type(self).__name__} is read only")


class AlbumInfo(BaseDictInfo):
    _KEYS_MAP = {
        "AlbumId": "album_id",
        "AlbumName": "album_name",
        "AlbumImageId": "album_image_id",
        "AlbumBigImageId": "album_big_image_id",
    }


class UserInfo(BaseDictInfo):
    _KEYS_MAP = {
        "UserId": "user_id",
        "UserName": "user_name",
    }


class GalleryInfo(BaseDictInfo):
    _KEYS_MAP = {
        "Classify": "category",
        "CommentCnt": "total_comments",
        "Content": "content",
        "CopyrightFlag": "copyright_flag",
        "CountryISOCode": "country_iso_code",
        "Date": "date",
        "FileId": "file_id",
        "FileName": "file_name",
        "FileTagArray": "file_tags",
        "FileType": "file_type",
        "FileURL": "file_url",
        "GalleryId": "gallery_id",
        "LikeCnt": "total_likes",
        "ShareCnt": "total_shares",
        "WatchCnt": "total_views",
        # Other observed keys (unused): AtList, CheckConfirm, CommentUTC, FillGameIsFinish,
        # FillGameScore, HideFlag, IsAddNew, IsAddRecommend, IsDel, IsFollow, IsLike,
        # LayerFileId, Level, LikeUTC, MusicFileId, OriginalGalleryId, PixelAmbId,
        # PixelAmbName, PrivateFlag, RegionId, UserHeaderId.
    }

    def __init__(self, info: dict):
        super().__init__(info)
        self.__dict__["user"] = UserInfo(info) if "UserId" in info else None
        dict.__init__(self, **self.__dict__)


# ---------------------------------------------------------------------------
# Experimental endpoint catalog (probed while mapping the API)
# ---------------------------------------------------------------------------
# Status legend: "working" confirmed to return data; "params" reachable but payload not
# figured out; "unknown"/"failed" as noted. Base host is app.divoom-gz.com. These are
# notes; the live client only wires up the endpoints in ``servoom.const.ApiEndpoint``.
# Superseded on 2026-09-29 by CLOUD_API.md, which maps the whole read side from the app's
# HTTP layer; entries below marked "promoted" now have DivoomClient methods.
EXPERIMENTAL_ENDPOINTS = {
    "GetMyUploadListV3": "promoted: DivoomClient.fetch_my_arts",
    "Cloud/GetLikeUserList": "promoted: DivoomClient.fetch_likes_for_art (token required)",
    "GetSomeoneInfoV2": "promoted: DivoomClient.fetch_someone_info (works anonymously)",
    "GetSomeoneListV3": "promoted: DivoomClient.fetch_someone_arts (V2 answers identically)",
    "SearchUser": "broken: ReturnCode 1 for every query (2026-09-24 and 2026-09-29)",
    "Comment/GetCommentListV3": "promoted: DivoomClient.fetch_comments_for_art (nested replies)",
    "GetCommentListV2": "working: flat gallery comments with ParentCommentId; V3 is nicer",
    "Forum/GetTag": "promoted: DivoomClient.fetch_forum_tags",
    "Forum/GetList": "promoted: DivoomClient.fetch_forum_posts; RegionId selects the feed",
    "Forum/GetForumUrl": "promoted: DivoomClient.fetch_ambassador_program_post (ignores ids, always post 102)",
    "Forum/GetCommentListV2": "promoted: DivoomClient.fetch_forum_comments (nested replies)",
    "Forum/GetCommentList": "working: flat V1 comment list, fewer fields than V2",
    "Forum/Like, Forum/CommentLike, Forum/ReportComment": "untested (write-side)",
    "Message/GetUnReadCnt": "promoted: DivoomClient.fetch_unread_counts",
    "Message/GetNotifyConfig": "promoted: DivoomClient.fetch_notify_config",
    "Message/GetLikeList": "promoted: DivoomClient.fetch_like_notifications",
    "Message/GetCommentList": "promoted: DivoomClient.fetch_comment_notifications",
    "Message/GetFansList": "promoted: DivoomClient.fetch_follower_notifications",
    "MessageGroup/GetGroupList": "promoted: DivoomClient.fetch_chat_groups (directory only)",
    "MessageGroup/Get{MessageList,List,History,GroupInfo,...}": "failed: ReturnCode 10, no such command",
    "Discover/GetTopNew": "promoted: DivoomClient.fetch_discover_top_new",
    "GetUserAllInfo": "promoted: DivoomClient.fetch_my_info",
    "GetNewLetterListV2": "promoted: DivoomClient.fetch_letters",
    "GetAnnouncement": "failed: ReturnCode 1",
    "Manager/GetReportGallery": "working",
    "Cloud/GalleryInfo": "promoted: DivoomClient.fetch_artwork_info (token required)",
    "Cloud/GetMatchInfo": "promoted: DivoomClient.fetch_match_info",
    "Tag/GetTagInfo": "promoted: DivoomClient.fetch_tag_info; payload {TagName}",
    "Tag/GetTagGalleryListV3": "promoted: DivoomClient.fetch_tag_gallery; {TagName, Mode} + filters",
    "Tag/SearchTagMoreV2": "promoted: DivoomClient.search_tag; Keywords (fuzzy) or TagKey (prefix)",
    "SearchGalleryV3": "promoted: DivoomClient.search_gallery; {Keywords, KeywordsEn} + filters",
    "GetCategoryFileListV2": "promoted: DivoomClient.fetch_category_files; page cap 30, see CLOUD_API.md",
    "GetFollowListV2": "promoted: DivoomClient.fetch_my_following (own account only; empty on the test account)",
    "Manager/GetReportCommentList": "failed: ReturnCode 1",
    "Manager/GetReportMessageGroupList": "failed: ReturnCode 1",
    "Manager/ShowGallery": "failed: GalleryId param causes ReturnCode 1",
    # 2026-09-29, from the app's command table (CLOUD_API.md has the details):
    "Channel/Store* (clock store), Sys/*, Photo/*, Alarm/*, ...": "ReturnCode 3 without a DeviceId bound to the account",
    "Cloud/GetFileData": "promoted: DivoomClient.fetch_legacy_preview (server-side 16x16 render, no token)",
    "Cloud/GetCategoryDataList, Cloud/GetSomeoneDataList": "web-only legacy 16x16 gallery with inline pixels; not wired",
    "User/GetPersonalInfo": "failed: server answers a PHP notice instead of JSON",
    "AI/GetPicListV2": "failed: server answers an SQL error",
    "GetStartLogo": "failed: ReturnCode 1",
    "GetCategoryFileList (V1)": "failed: ReturnCode 3 whatever is sent",
}

# Extra payload fields observed on Manager/GetReportGallery-style calls, kept for reference
# (the values used during probing were tied to one specific gallery/comment and are not
# reusable as-is): GroupId="I2", GroupName="Feedback & Suggestion", ChannelId="busChannel".
# Those three are chat-room identifiers from MessageGroup/GetGroupList (see FORUM_API.md).
