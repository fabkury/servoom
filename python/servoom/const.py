"""Live constants used by the Divoom client: servers, API endpoint paths, gallery filters.

Only endpoints the client actually calls live here. Observed-but-unused endpoints and
raw-record mappers are preserved in ``servoom.gallery_reference``. The endpoint map with
request/response fields, page caps and auth requirements is in CLOUD_API.md and
FORUM_API.md at the repo root.
"""

from enum import Enum, IntFlag


class Server(str, Enum):
    API = "app.divoom-gz.com"
    FILE = "f.divoom-gz.com"


class ApiEndpoint(str, Enum):
    """API endpoint paths (joined with ``Server.API``)."""

    USER_LOGIN = "/UserLogin"
    GET_USER_ALL_INFO = "/GetUserAllInfo"
    # -- artworks (CLOUD_API.md) --
    GET_GALLERY_INFO = "/Cloud/GalleryInfo"
    GET_LEGACY_PREVIEW = "/Cloud/GetFileData"  # server-side 16x16 render, legacy formats
    GET_MY_UPLOADS = "/GetMyUploadListV3"
    GET_MY_LIKES = "/GetMyLikeListV3"
    GET_LIKE_USERS = "/Cloud/GetLikeUserList"
    GET_SOMEONE_INFO = "/GetSomeoneInfoV2"
    GET_SOMEONE_LIST = "/GetSomeoneListV3"  # the app's current call; V2 answers identically
    GET_CATEGORY_FILES = "/GetCategoryFileListV2"
    GET_EXPERT_GALLERY = "/Cloud/GetExpertGallery"
    SEARCH_USER = "/SearchUser"  # broken server-side (ReturnCode 1 for every query)
    SEARCH_TAG = "/Tag/SearchTagMoreV2"
    SUGGEST_TAG = "/Tag/SearchTagSimple"
    SEARCH_GALLERY = "/SearchGalleryV3"
    GET_TAG_INFO = "/Tag/GetTagInfo"
    GET_TAG_GALLERY = "/Tag/GetTagGalleryListV3"
    GET_TAG_USERS = "/Tag/GetUserList"
    GET_HOT_TAGS = "/Cloud/GetHotTag"
    GET_ART_COMMENTS = "/Comment/GetCommentListV3"
    # -- users --
    GET_USER_SCORE = "/LookScore"
    GET_USER_MEDALS = "/Medal/GetList"
    GET_EXPERTS = "/GetExpertListV4"
    GET_HOT_EXPERTS = "/Cloud/GetHotExpert"
    GET_MY_FOLLOWERS = "/GetFansListV2"
    GET_MY_FOLLOWING = "/GetFollowListV2"
    GET_BLACKLIST = "/User/GetBlackList"
    # -- playlists --
    GET_USER_PLAYLISTS = "/Playlist/GetSomeOneList"
    GET_MY_PLAYLISTS = "/Playlist/GetMyList"
    GET_USER_PLAYLIST_ARTS = "/Playlist/GetSomeOneImageList"
    GET_MY_PLAYLIST_ARTS = "/Playlist/GetMyImageList"
    # -- discovery --
    GET_ALBUMS = "/Discover/GetAlbumListV3"
    GET_ALBUM_INFO = "/Discover/GetAlbumInfo"
    GET_ALBUM_ARTS = "/Discover/GetAlbumImageListV3"
    GET_DISCOVER_THEMES = "/Discover/GetTheme"
    GET_DISCOVER_TOP_NEW = "/Discover/GetTopNew"
    GET_MATCH_INFO = "/Cloud/GetMatchInfo"
    # Forum = the official article feed shown in the app (see FORUM_API.md at the repo root).
    FORUM_GET_TAG = "/Forum/GetTag"
    FORUM_GET_LIST = "/Forum/GetList"
    FORUM_GET_AMBASSADOR_POST = "/Forum/GetForumUrl"  # fixed pointer to post 102
    FORUM_GET_COMMENTS = "/Forum/GetCommentListV2"
    # Notification inbox ("Message" tab), private chats, letters and chat-room directory.
    MESSAGE_GET_UNREAD_CNT = "/Message/GetUnReadCnt"
    MESSAGE_GET_NOTIFY_CONFIG = "/Message/GetNotifyConfig"
    MESSAGE_GET_LIKE_LIST = "/Message/GetLikeList"
    MESSAGE_GET_COMMENT_LIST = "/Message/GetCommentList"
    MESSAGE_GET_FANS_LIST = "/Message/GetFansList"
    MESSAGE_GET_CONVERSATIONS = "/Message/GetConversationList"
    MESSAGE_GET_LETTERS = "/GetNewLetterListV2"
    MESSAGE_GROUP_GET_GROUP_LIST = "/MessageGroup/GetGroupList"


#: Endpoints verified (2026-09-29) to answer with no ``Token``/``UserId`` at all. The
#: anonymous client warns when it calls anything else. See CLOUD_API.md.
ANONYMOUS_ENDPOINTS = frozenset({
    ApiEndpoint.GET_LEGACY_PREVIEW,
    ApiEndpoint.GET_SOMEONE_INFO,
    ApiEndpoint.GET_SOMEONE_LIST,
    ApiEndpoint.GET_CATEGORY_FILES,
    ApiEndpoint.GET_EXPERT_GALLERY,
    ApiEndpoint.SEARCH_TAG,
    ApiEndpoint.SEARCH_GALLERY,
    ApiEndpoint.GET_ART_COMMENTS,
    ApiEndpoint.GET_USER_SCORE,
    ApiEndpoint.GET_USER_MEDALS,
    ApiEndpoint.GET_EXPERTS,
    ApiEndpoint.GET_HOT_EXPERTS,
    ApiEndpoint.GET_ALBUMS,
    ApiEndpoint.GET_ALBUM_INFO,
    ApiEndpoint.GET_ALBUM_ARTS,
    ApiEndpoint.GET_MATCH_INFO,
    ApiEndpoint.FORUM_GET_LIST,
})


class GallerySort(int, Enum):
    """``FileSort`` on gallery listings."""

    LATEST = 0
    POPULAR = 1


class GallerySize(IntFlag):
    """``FileSize`` bitmask on gallery listings (combine with ``|``; ``ALL`` = 127).

    Bit 8 is not selectable in the app; Planet-lamp artworks (``GalleryCategory.PLANET``)
    report ``FileSize 8`` on their records.
    """

    W16 = 1
    W32 = 2
    W64 = 4
    W128 = 16
    W256 = 32
    W256_CIRCLE = 64
    ALL = 127


class GalleryFileType(int, Enum):
    """``FileType`` filter on gallery listings (the server's own classification)."""

    PICTURE = 0
    ANIMATION = 1
    MULTI_PICTURE = 2
    MULTI_ANIMATION = 3
    LED_TEXT = 4
    ALL = 5
    SAND = 6


class GalleryCategory(int, Enum):
    """``Classify`` ids with the tab names the app shows (CLOUD_API.md has the full table,
    including the hidden ids that still filter)."""

    NEW = 0
    DEFAULT = 1
    LED_TEXT = 2  # hidden
    CHARACTER = 3
    EMOJI = 4
    DAILY = 5
    NATURE = 6
    ICON = 7
    PATTERN = 8
    CREATIVE = 9
    PHOTO = 12
    GADGET = 15
    BUSINESS = 16
    SEASON = 17
    RECOMMEND = 18
    PLANET = 19  # 28-LED lamp artworks, FileType 9 / FileSize 8
    FOLLOW = 20  # uploads of followed users; token required
    PIXEL_COLORING = 29
    PIXEL_MATCH = 30  # the running contest, see fetch_match_info()
    PLANT = 31
    ANIMAL = 32
    HUMAN = 33
    EMOJI_2 = 34
    FOOD = 35
    OTHERS = 36
    AI = 40


class ForumRegion(int, Enum):
    """``RegionId`` values that select a forum feed.

    The server keeps two independent article feeds. Any ``RegionId`` other than 86 (an
    explicit 0 included) returns the international/English feed; 86 returns the Chinese
    one. Omitting the field falls back to the account's own region, and accounts
    registered through the API carry ``RegionId 0``, which the server then treats as China.
    """

    INTERNATIONAL = 1
    CHINA = 86
