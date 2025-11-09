"""
Configuration constants for the Divoom API client.
"""


class Config:
    """Configuration constants for the Divoom API client."""
    
    # API Endpoints
    # Note: Endpoint URLs are confirmed. Payload parameters need to be configured
    # in the respective methods (marked with TODO comments).
    MY_ARTS_ENDPOINT = 'https://app.divoom-gz.com/GetMyUploadListV3'  # ✓ Working
    MY_LIKES_ENDPOINT = 'https://app.divoom-gz.com/Cloud/GetLikeUserList'  # ✓ Working
    SOMEONE_INFO_ENDPOINT = 'https://app.divoom-gz.com/GetSomeoneInfoV2'  # ✓ Working
    SOMEONE_LIST_ENDPOINT = 'https://app.divoom-gz.com/GetSomeoneListV2'  # ✓ Working
    TAG_INFO_ENDPOINT = 'https://app.divoom-gz.com/Tag/GetTagInfo'  # TODO: Configure params
    TAG_LIST_ENDPOINT = 'https://app.divoom-gz.com/Tag/GetTagGalleryListV3'  # TODO: Configure params
    SEARCH_USER_ENDPOINT = 'https://app.divoom-gz.com/SearchUser'  # ✓ Working
    SEARCH_TAG_ENDPOINT = 'https://app.divoom-gz.com/Tag/SearchTagMoreV2'  # TODO: Configure params
    SEARCH_GALLERY_ENDPOINT = 'https://app.divoom-gz.com/SearchGalleryV3'  # TODO: Configure params
    GET_CATEGORY_FILES_ENDPOINT = 'https://app.divoom-gz.com/GetCategoryFileListV2'  # TODO: Configure params
    GET_COMMENT_LIST_ENDPOINT = 'https://app.divoom-gz.com/Comment/GetCommentListV3' # Working
    # GET_COMMENT_LIST_ENDPOINT = "https://app.divoom-gz.com/GetCommentListV2" # Working
    GET_FORUM_URL_ENDPOINT = "https://app.divoom-gz.com/Forum/GetForumUrl" # Working
    MANAGER_GET_REPORT_GALLERY = "https://app.divoom-gz.com/Manager/GetReportGallery" # Working
    
    # MANAGER_GET_REPORT_GALLERY = "https://app.divoom-gz.com/Manager/GetUserInfo"
    # MANAGER_GET_REPORT_GALLERY = "https://app.divoom-gz.com/Manager/GetReportCommentList" # 1 Failed
    # MANAGER_GET_REPORT_GALLERY = "https://app.divoom-gz.com/Manager/GetReportUserList"
    # MANAGER_GET_REPORT_GALLERY = "https://app.divoom-gz.com/Manager/ShowGallery" # 'GalleryId': causes error code 1
    # MANAGER_GET_REPORT_GALLERY = "https://app.divoom-gz.com/Manager/AddGood"
    # MANAGER_GET_REPORT_GALLERY = "https://app.divoom-gz.com/Manager/GetReportMessageGroupList" # 1 Failed
    # MANAGER_GET_REPORT_GALLERY = "https://app.divoom-gz.com/Manager/PassGallery" ?
    # MANAGER_GET_REPORT_GALLERY = "https://app.divoom-gz.com/MessageGroup/GetGroupList" # Working
    # MANAGER_GET_REPORT_GALLERY = "https://app.divoom-gz.com/Forum/GetList" # Working   
    # MANAGER_GET_REPORT_GALLERY = "https://app.divoom-gz.com/GetFollowListV2" # 0, empty list
    # MANAGER_GET_REPORT_GALLERY = "https://app.divoom-gz.com/Cloud/GalleryInfo" # Working
    # MANAGER_GET_REPORT_GALLERY = "https://app.divoom-gz.com/Message/GetLikeList" # 0, empty list
    # MANAGER_GET_REPORT_GALLERY = "https://app.divoom-gz.com/Cloud/GetMatchInfo" # Returns "Paws2025"
    # MANAGER_GET_REPORT_GALLERY = "https://app.divoom-gz.com/Forum/Like"
    DEBUG_FETCH_ENDPOINT = "https://app.divoom-gz.com/Cloud/GetMatchInfo"
    # "GroupId": "I2",
    # "GroupName": "Feedback & Suggestion",
    # "ChannelId": "busChannel",
    
    # Test credentials
    EMAIL = 'email@server.com'
    MD5_PASSWORD = 'INSERT-THE-MD5-HASH-OF-THE-PASSWORD-HERE-NOT-THE-PASSWORD-ITSELF'
    
    # Query parameters
    BATCH_SIZE = 50
    MAX_RETRIES = 3
    REQUEST_TIMEOUT = 10
    RETRY_DELAY = 1  # seconds
    LIKES_REPORT_INTERVAL = 1000
    

    DEBUG_MODE = True
    DEBUG_LIMIT = 50
    
    # Output directory
    OUTPUT_DIR = 'out'
    
    # HTTP Headers (from apixoo)
    HEADERS = {
        'User-Agent': 'Aurabox/3.1.10 (iPad; iOS 14.8; Scale/2.00)',
        'Content-Type': 'application/json'
    }
    
    # File size filters (bitmap flags)
    FILE_SIZE_FILTER = 0b1 | 0b10 | 0b100 | 0b1000 | 0b10000 | 0b100000
    
    # Field mappings for output
    FIELD_MAPPINGS = {
        "IsLike": "Is Like",
        "GalleryId": "Gallery ID",
        "UserId": "User ID",
        "PixelAmbId": "Pixel Amb ID",
        "PixelAmbName": "Pixel Amb Name",
        "UserName": "User Name",
        "UserHeaderId": "User Header ID",
        "Level": "Level",
        "RegionId": "Region ID",
        "CountryISOCode": "Country ISO Code",
        "IsFollow": "Is Follow",
        "LikeUTC": "Like UTC",
        "CommentUTC": "Comment UTC",
        "AtList": "At List",
        "ShareCnt": "Share Count",
        "Content": "Content",
        "FileTagArray": "File Tag Array",
        "PrivateFlag": "Private Flag",
        "CopyrightFlag": "Copyright Flag",
        "IsDel": "Is Deleted",
        "CheckConfirm": "Check Confirm",
        "FileType": "File Type",
        "LikeCnt": "Like Count",
        "WatchCnt": "Watch Count",
        "Classify": "Classify",
        "FillGameScore": "Fill Game Score",
        "OriginalGalleryId": "Original Gallery ID",
        "FileName": "File Name",
        "FileSize": "File Size",
        "HideFlag": "Hide Flag",
        "IsAddNew": "Is Add New",
        "IsAddRecommend": "Is Add Recommend",
        "Date": "Creation",
        "CommentCnt": "Comment Count",
        "FileId": "File ID",
        "MusicFileId": "Music File ID",
        "LayerFileId": "Layer File ID",
        "FileURL": "File URL",
        "FillGameIsFinish": "Fill Game Is Finish",
        "AIFlag": "AI Flag"
    }

