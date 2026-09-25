"""Live constants used by the Divoom client: servers and API endpoint paths.

Only endpoints the client actually calls live here. Observed-but-unused endpoints, gallery
enumerations and raw-record mappers are preserved in ``servoom.gallery_reference``.
"""

from enum import Enum


class Server(str, Enum):
    API = "app.divoom-gz.com"
    FILE = "f.divoom-gz.com"


class ApiEndpoint(str, Enum):
    """API endpoint paths (joined with ``Server.API``)."""

    USER_LOGIN = "/UserLogin"
    GET_GALLERY_INFO = "/Cloud/GalleryInfo"
    GET_MY_UPLOADS = "/GetMyUploadListV3"
    GET_LIKE_USERS = "/Cloud/GetLikeUserList"
    GET_SOMEONE_INFO = "/GetSomeoneInfoV2"
    GET_SOMEONE_LIST = "/GetSomeoneListV2"
    GET_CATEGORY_FILES = "/GetCategoryFileListV2"
    SEARCH_USER = "/SearchUser"
    SEARCH_TAG = "/Tag/SearchTagMoreV2"
    SEARCH_GALLERY = "/SearchGalleryV3"
    GET_TAG_INFO = "/Tag/GetTagInfo"
    GET_TAG_GALLERY = "/Tag/GetTagGalleryListV3"
    GET_ART_COMMENTS = "/Comment/GetCommentListV3"
    # Forum = the official article feed shown in the app (see FORUM_API.md at the repo root).
    FORUM_GET_TAG = "/Forum/GetTag"
    FORUM_GET_LIST = "/Forum/GetList"
    FORUM_GET_AMBASSADOR_POST = "/Forum/GetForumUrl"  # fixed pointer to post 102
    FORUM_GET_COMMENTS = "/Forum/GetCommentListV2"
    # Notification inbox ("Message" tab) and community chat-room directory.
    MESSAGE_GET_UNREAD_CNT = "/Message/GetUnReadCnt"
    MESSAGE_GET_NOTIFY_CONFIG = "/Message/GetNotifyConfig"
    MESSAGE_GET_LIKE_LIST = "/Message/GetLikeList"
    MESSAGE_GET_COMMENT_LIST = "/Message/GetCommentList"
    MESSAGE_GET_FANS_LIST = "/Message/GetFansList"
    MESSAGE_GROUP_GET_GROUP_LIST = "/MessageGroup/GetGroupList"


class ForumRegion(int, Enum):
    """``RegionId`` values that select a forum feed.

    The server keeps two independent article feeds. Any ``RegionId`` other than 86 (an
    explicit 0 included) returns the international/English feed; 86 returns the Chinese
    one. Omitting the field falls back to the account's own region, and accounts
    registered through the API carry ``RegionId 0``, which the server then treats as China.
    """

    INTERNATIONAL = 1
    CHINA = 86
