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
class GalleryCategory(int, Enum):
    """``Classify`` values seen on gallery listings. Commented entries were observed but
    not confirmed / not useful and are kept for the record."""

    NEW = 0
    DEFAULT = 1
    # LED_TEXT = 2
    CHARACTER = 3
    EMOJI = 4
    DAILY = 5
    NATURE = 6
    SYMBOL = 7
    PATTERN = 8
    CREATIVE = 9
    PHOTO = 12
    TOP = 14
    GADGET = 15
    BUSINESS = 16
    FESTIVAL = 17
    RECOMMEND = 18
    # PLANET = 19
    FOLLOW = 20
    # REVIEW_PHOTOS = 21
    # REVIEW_STOLEN_PHOTOS = 22
    # FILL_GAME = 29
    PIXEL_MATCH = 30  # event-dependent
    PLANT = 31
    ANIMAL = 32
    PERSON = 33
    EMOJI_2 = 34
    FOOD = 35
    # OTHERS = 36
    # REPORT_PHOTO = 254
    # CREATION_ALBUM = 255


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


class GallerySorting(int, Enum):
    NEW_UPLOAD = 0
    MOST_LIKED = 1


class GalleryDimension(int, Enum):
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
EXPERIMENTAL_ENDPOINTS = {
    "GetMyUploadListV3": "working",
    "Cloud/GetLikeUserList": "working",
    "GetSomeoneInfoV2": "working",
    "GetSomeoneListV2": "working",
    "SearchUser": "working",
    "Comment/GetCommentListV3": "working",
    "Forum/GetForumUrl": "working",
    "Manager/GetReportGallery": "working",
    "Cloud/GalleryInfo": "working",
    "Cloud/GetMatchInfo": 'working; returns current event name (e.g. "Paws2025")',
    "MessageGroup/GetGroupList": "working",
    "Forum/GetList": "working",
    "Tag/GetTagInfo": "params — reachable, payload TBD",
    "Tag/GetTagGalleryListV3": "params — reachable, payload TBD",
    "Tag/SearchTagMoreV2": "params — reachable, payload TBD",
    "SearchGalleryV3": "params — reachable, payload TBD",
    "GetCategoryFileListV2": "params — reachable, payload TBD",
    "GetFollowListV2": "empty — returned 0 / empty list",
    "Message/GetLikeList": "empty — returned 0 / empty list",
    "Manager/GetReportCommentList": "failed — ReturnCode 1",
    "Manager/GetReportMessageGroupList": "failed — ReturnCode 1",
    "Manager/ShowGallery": "failed — GalleryId param causes ReturnCode 1",
}

# Extra payload fields observed on Manager/GetReportGallery-style calls, kept for reference
# (the values used during probing were tied to one specific gallery/comment and are not
# reusable as-is): GroupId="I2", GroupName="Feedback & Suggestion", ChannelId="busChannel".
