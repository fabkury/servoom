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
