/* Endpoint table: paths, list keys and anonymous access, mirroring servoom.const
 * (ApiEndpoint + ANONYMOUS_ENDPOINTS). Documented in CLOUD_API.md / FORUM_API.md. */
#include "servoom/client.h"

static const char *const K_FILELIST[] = {"FileList", NULL};
static const char *const K_CATEGORY[] = {"FileList", "CategoryFileList", NULL};
static const char *const K_USERLIST[] = {"UserList", NULL};
static const char *const K_TAGLIST[] = {"TagList", NULL};
static const char *const K_COMMENTS[] = {"CommentList", NULL};
static const char *const K_EXPERTS[] = {"ExpertList", NULL};
static const char *const K_FOLLOW[] = {"FollowList", NULL};
static const char *const K_BLACK[] = {"BlackList", NULL};
static const char *const K_PLAYLIST[] = {"PlayList", NULL};
static const char *const K_ALBUMS[] = {"AlbumList", NULL};
static const char *const K_FORUM[] = {"ForumList", NULL};
static const char *const K_LIKELIST[] = {"LikeList", NULL};
static const char *const K_LETTERS[] = {"LetterList", NULL};

#define EP(name, path, keys, anon) {name, path, keys, anon}

static const servoom_endpoint_info TABLE[SERVOOM_EP__COUNT] = {
    EP("USER_LOGIN", "/UserLogin", NULL, 0),
    EP("GET_USER_ALL_INFO", "/GetUserAllInfo", NULL, 0),
    /* artworks */
    EP("GET_GALLERY_INFO", "/Cloud/GalleryInfo", NULL, 0),
    EP("GET_LEGACY_PREVIEW", "/Cloud/GetFileData", NULL, 1),
    EP("GET_MY_UPLOADS", "/GetMyUploadListV3", K_FILELIST, 0),
    EP("GET_MY_LIKES", "/GetMyLikeListV3", K_FILELIST, 0),
    EP("GET_LIKE_USERS", "/Cloud/GetLikeUserList", K_USERLIST, 0),
    EP("GET_SOMEONE_INFO", "/GetSomeoneInfoV2", NULL, 1),
    EP("GET_SOMEONE_LIST", "/GetSomeoneListV3", K_FILELIST, 1),
    EP("GET_CATEGORY_FILES", "/GetCategoryFileListV2", K_CATEGORY, 1),
    EP("GET_EXPERT_GALLERY", "/Cloud/GetExpertGallery", K_FILELIST, 1),
    EP("SEARCH_USER", "/SearchUser", K_USERLIST, 0),
    EP("SEARCH_TAG", "/Tag/SearchTagMoreV2", K_TAGLIST, 1),
    EP("SUGGEST_TAG", "/Tag/SearchTagSimple", K_TAGLIST, 0),
    EP("SEARCH_GALLERY", "/SearchGalleryV3", K_FILELIST, 1),
    EP("GET_TAG_INFO", "/Tag/GetTagInfo", NULL, 0),
    EP("GET_TAG_GALLERY", "/Tag/GetTagGalleryListV3", K_FILELIST, 0),
    EP("GET_TAG_USERS", "/Tag/GetUserList", K_USERLIST, 0),
    EP("GET_HOT_TAGS", "/Cloud/GetHotTag", K_TAGLIST, 0),
    EP("GET_ART_COMMENTS", "/Comment/GetCommentListV3", K_COMMENTS, 1),
    /* users */
    EP("GET_USER_SCORE", "/LookScore", NULL, 1),
    EP("GET_USER_MEDALS", "/Medal/GetList", NULL, 1),
    EP("GET_EXPERTS", "/GetExpertListV4", K_EXPERTS, 1),
    EP("GET_HOT_EXPERTS", "/Cloud/GetHotExpert", K_EXPERTS, 1),
    EP("GET_MY_FOLLOWERS", "/GetFansListV2", K_FOLLOW, 0),
    EP("GET_MY_FOLLOWING", "/GetFollowListV2", K_FOLLOW, 0),
    EP("GET_BLACKLIST", "/User/GetBlackList", K_BLACK, 0),
    /* playlists */
    EP("GET_USER_PLAYLISTS", "/Playlist/GetSomeOneList", K_PLAYLIST, 0),
    EP("GET_MY_PLAYLISTS", "/Playlist/GetMyList", K_PLAYLIST, 0),
    EP("GET_USER_PLAYLIST_ARTS", "/Playlist/GetSomeOneImageList", K_FILELIST, 0),
    EP("GET_MY_PLAYLIST_ARTS", "/Playlist/GetMyImageList", K_FILELIST, 0),
    /* discovery */
    EP("GET_ALBUMS", "/Discover/GetAlbumListV3", K_ALBUMS, 1),
    EP("GET_ALBUM_INFO", "/Discover/GetAlbumInfo", NULL, 1),
    EP("GET_ALBUM_ARTS", "/Discover/GetAlbumImageListV3", K_FILELIST, 1),
    EP("GET_DISCOVER_THEMES", "/Discover/GetTheme", NULL, 0),
    EP("GET_DISCOVER_TOP_NEW", "/Discover/GetTopNew", NULL, 0),
    EP("GET_MATCH_INFO", "/Cloud/GetMatchInfo", NULL, 1),
    /* forum */
    EP("FORUM_GET_TAG", "/Forum/GetTag", K_TAGLIST, 0),
    EP("FORUM_GET_LIST", "/Forum/GetList", K_FORUM, 1),
    EP("FORUM_GET_AMBASSADOR_POST", "/Forum/GetForumUrl", NULL, 0),
    EP("FORUM_GET_COMMENTS", "/Forum/GetCommentListV2", K_COMMENTS, 0),
    /* inbox */
    EP("MESSAGE_GET_UNREAD_CNT", "/Message/GetUnReadCnt", NULL, 0),
    EP("MESSAGE_GET_NOTIFY_CONFIG", "/Message/GetNotifyConfig", NULL, 0),
    EP("MESSAGE_GET_LIKE_LIST", "/Message/GetLikeList", K_LIKELIST, 0),
    EP("MESSAGE_GET_COMMENT_LIST", "/Message/GetCommentList", K_LIKELIST, 0),
    EP("MESSAGE_GET_FANS_LIST", "/Message/GetFansList", K_LIKELIST, 0),
    EP("MESSAGE_GET_CONVERSATIONS", "/Message/GetConversationList", NULL, 0),
    EP("MESSAGE_GET_LETTERS", "/GetNewLetterListV2", K_LETTERS, 0),
    EP("MESSAGE_GROUP_GET_GROUP_LIST", "/MessageGroup/GetGroupList", NULL, 0),
};

const servoom_endpoint_info *servoom_endpoint_get(servoom_endpoint ep)
{
    if ((int)ep < 0 || ep >= SERVOOM_EP__COUNT)
        return NULL;
    return &TABLE[ep];
}
