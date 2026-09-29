/* Divoom cloud client: login, gallery lookups, paginated listings and file downloads.
 *
 * Port of servoom.client.DivoomClient / servoom.http / servoom.const. Requests are JSON
 * POSTs to app.divoom-gz.com; files are fetched from f.divoom-gz.com. Responses are handed
 * back as cJSON trees (vendored, see third_party/cJSON) that the caller owns and frees with
 * cJSON_Delete(). The endpoint map (fields, page caps, which calls need a token) is in
 * CLOUD_API.md and FORUM_API.md at the repository root.
 *
 * Only available when the library is built with SERVOOM_WITH_CLIENT (the default); the
 * functions still exist otherwise and return SERVOOM_ERR_UNSUPPORTED.
 */
#ifndef SERVOOM_CLIENT_H
#define SERVOOM_CLIENT_H

#include <stddef.h>
#include <stdint.h>
#include "servoom/status.h"
#include "cJSON.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct servoom_client servoom_client;

/* ---- constants (servoom.const) ------------------------------------------- */

/* FileSort on gallery listings. */
typedef enum servoom_gallery_sort {
    SERVOOM_SORT_LATEST = 0,
    SERVOOM_SORT_POPULAR = 1
} servoom_gallery_sort;

/* FileSize bitmask on gallery listings (OR them; SERVOOM_SIZE_ALL = 127). Bit 8 is not
 * selectable in the app; Planet-lamp records report FileSize 8. */
enum servoom_gallery_size {
    SERVOOM_SIZE_16 = 1,
    SERVOOM_SIZE_32 = 2,
    SERVOOM_SIZE_64 = 4,
    SERVOOM_SIZE_128 = 16,
    SERVOOM_SIZE_256 = 32,
    SERVOOM_SIZE_256_CIRCLE = 64,
    SERVOOM_SIZE_ALL = 127
};

/* FileType filter (the server's own classification). */
typedef enum servoom_gallery_file_type {
    SERVOOM_FILETYPE_PICTURE = 0,
    SERVOOM_FILETYPE_ANIMATION = 1,
    SERVOOM_FILETYPE_MULTI_PICTURE = 2,
    SERVOOM_FILETYPE_MULTI_ANIMATION = 3,
    SERVOOM_FILETYPE_LED_TEXT = 4,
    SERVOOM_FILETYPE_ALL = 5,
    SERVOOM_FILETYPE_SAND = 6
} servoom_gallery_file_type;

/* Classify ids with the tab names the app shows (CLOUD_API.md lists the hidden ones too). */
typedef enum servoom_gallery_category {
    SERVOOM_CAT_NEW = 0,
    SERVOOM_CAT_DEFAULT = 1,
    SERVOOM_CAT_LED_TEXT = 2,
    SERVOOM_CAT_CHARACTER = 3,
    SERVOOM_CAT_EMOJI = 4,
    SERVOOM_CAT_DAILY = 5,
    SERVOOM_CAT_NATURE = 6,
    SERVOOM_CAT_ICON = 7,
    SERVOOM_CAT_PATTERN = 8,
    SERVOOM_CAT_CREATIVE = 9,
    SERVOOM_CAT_PHOTO = 12,
    SERVOOM_CAT_GADGET = 15,
    SERVOOM_CAT_BUSINESS = 16,
    SERVOOM_CAT_SEASON = 17,
    SERVOOM_CAT_RECOMMEND = 18,
    SERVOOM_CAT_PLANET = 19,
    SERVOOM_CAT_FOLLOW = 20,
    SERVOOM_CAT_REVIEW_QUEUE = 21, /* held uploads awaiting photo review; token required */
    SERVOOM_CAT_PIXEL_COLORING = 29,
    SERVOOM_CAT_PIXEL_MATCH = 30,
    SERVOOM_CAT_PLANT = 31,
    SERVOOM_CAT_ANIMAL = 32,
    SERVOOM_CAT_HUMAN = 33,
    SERVOOM_CAT_EMOJI_2 = 34,
    SERVOOM_CAT_FOOD = 35,
    SERVOOM_CAT_OTHERS = 36,
    SERVOOM_CAT_AI = 40
} servoom_gallery_category;

/* RegionId values that select a forum feed (FORUM_API.md). */
typedef enum servoom_forum_region {
    SERVOOM_REGION_INTERNATIONAL = 1,
    SERVOOM_REGION_CHINA = 86
} servoom_forum_region;

/* Every endpoint the client knows (servoom.const.ApiEndpoint). */
typedef enum servoom_endpoint {
    SERVOOM_EP_USER_LOGIN,
    SERVOOM_EP_USER_ALL_INFO,
    /* artworks */
    SERVOOM_EP_GALLERY_INFO,
    SERVOOM_EP_LEGACY_PREVIEW,
    SERVOOM_EP_MY_UPLOADS,
    SERVOOM_EP_MY_LIKES,
    SERVOOM_EP_LIKE_USERS,
    SERVOOM_EP_SOMEONE_INFO,
    SERVOOM_EP_SOMEONE_LIST,
    SERVOOM_EP_CATEGORY_FILES,
    SERVOOM_EP_EXPERT_GALLERY,
    SERVOOM_EP_SEARCH_USER,
    SERVOOM_EP_SEARCH_TAG,
    SERVOOM_EP_SUGGEST_TAG,
    SERVOOM_EP_SEARCH_GALLERY,
    SERVOOM_EP_TAG_INFO,
    SERVOOM_EP_TAG_GALLERY,
    SERVOOM_EP_TAG_USERS,
    SERVOOM_EP_HOT_TAGS,
    SERVOOM_EP_ART_COMMENTS,
    /* users */
    SERVOOM_EP_USER_SCORE,
    SERVOOM_EP_USER_MEDALS,
    SERVOOM_EP_EXPERTS,
    SERVOOM_EP_HOT_EXPERTS,
    SERVOOM_EP_MY_FOLLOWERS,
    SERVOOM_EP_MY_FOLLOWING,
    SERVOOM_EP_BLACKLIST,
    /* playlists */
    SERVOOM_EP_USER_PLAYLISTS,
    SERVOOM_EP_MY_PLAYLISTS,
    SERVOOM_EP_USER_PLAYLIST_ARTS,
    SERVOOM_EP_MY_PLAYLIST_ARTS,
    /* discovery */
    SERVOOM_EP_ALBUMS,
    SERVOOM_EP_ALBUM_INFO,
    SERVOOM_EP_ALBUM_ARTS,
    SERVOOM_EP_DISCOVER_THEMES,
    SERVOOM_EP_DISCOVER_TOP_NEW,
    SERVOOM_EP_MATCH_INFO,
    /* forum */
    SERVOOM_EP_FORUM_TAGS,
    SERVOOM_EP_FORUM_LIST,
    SERVOOM_EP_FORUM_AMBASSADOR_POST,
    SERVOOM_EP_FORUM_COMMENTS,
    /* inbox */
    SERVOOM_EP_MESSAGE_UNREAD_CNT,
    SERVOOM_EP_MESSAGE_NOTIFY_CONFIG,
    SERVOOM_EP_MESSAGE_LIKE_LIST,
    SERVOOM_EP_MESSAGE_COMMENT_LIST,
    SERVOOM_EP_MESSAGE_FANS_LIST,
    SERVOOM_EP_MESSAGE_CONVERSATIONS,
    SERVOOM_EP_MESSAGE_LETTERS,
    SERVOOM_EP_MESSAGE_GROUP_LIST,
    SERVOOM_EP__COUNT
} servoom_endpoint;

typedef struct servoom_endpoint_info {
    const char *name;             /* Python ApiEndpoint member name, e.g. "GET_ALBUMS" */
    const char *path;             /* "/Discover/GetAlbumListV3" */
    const char *const *list_keys; /* NULL-terminated response keys that hold the items; NULL for lookups */
    int anonymous_ok;             /* verified to answer with no Token/UserId (CLOUD_API.md) */
} servoom_endpoint_info;

/* Static metadata for `ep`; NULL when out of range. */
const servoom_endpoint_info *servoom_endpoint_get(servoom_endpoint ep);

/* ---- client --------------------------------------------------------------- */

typedef struct servoom_client_settings {
    int batch_size;         /* listing window size per request (default 40) */
    int max_retries;        /* transport retries (default 3) */
    int timeout_seconds;    /* per request (default 10) */
    int retry_delay_ms;     /* pause between retries (default 1000) */
    int respect_hide_flag;  /* drop items with HideFlag set (default 1) */
    int file_size_filter;   /* FileSize bitmask for listings (default 0b111111 = all sizes) */
    const char *user_agent; /* default "Aurabox/3.1.10 (iPad; iOS 14.8; Scale/2.00)" */
} servoom_client_settings;

/* Fill `s` with the defaults the Python client uses. */
void servoom_client_settings_default(servoom_client_settings *s);

/* `md5_password` is the 32-char hex MD5 of the plain password (see servoom_md5_hex).
 * `settings` may be NULL for defaults. Returns NULL on allocation failure. */
servoom_client *servoom_client_new(const char *email, const char *md5_password,
                                   const servoom_client_settings *settings);

/* A client without credentials: it sends no Token/UserId and never logs in. The endpoints
 * flagged anonymous_ok in the table answer that way; the others get ReturnCode 11 or an
 * empty list from the server (Python DivoomClient(anonymous=True)). */
servoom_client *servoom_client_new_anonymous(const servoom_client_settings *settings);
int servoom_client_is_anonymous(const servoom_client *client);

void servoom_client_free(servoom_client *client);

/* SERVOOM_ERR_STATE for an anonymous client. */
servoom_status servoom_client_login(servoom_client *client);
int servoom_client_is_logged_in(const servoom_client *client);
int64_t servoom_client_user_id(const servoom_client *client);
const char *servoom_client_token(const servoom_client *client);

/* Last error detail (transport message or the API's ReturnMessage); static per client. */
const char *servoom_client_last_error(const servoom_client *client);

/* Raw authenticated POST: `payload` (may be NULL) gets Token/UserId merged in (nothing for
 * an anonymous client). The parsed response is returned in *out regardless of ReturnCode;
 * the status is SERVOOM_ERR_API when ReturnCode != 0. */
servoom_status servoom_client_post(servoom_client *client, const char *path,
                                   const cJSON *payload, cJSON **out);

/* ---- generic calls over the endpoint table -------------------------------- */

typedef int (*servoom_item_fn)(const cJSON *item, void *userdata);

/* Single-shot call: *out is the whole response when ReturnCode == 0, else NULL and
 * SERVOOM_ERR_API (Python _lookup -> None). `payload` may be NULL. */
servoom_status servoom_client_lookup(servoom_client *client, servoom_endpoint ep,
                                     const cJSON *payload, cJSON **out);

/* Paginated listing with StartNum/EndNum windows (Python servoom.http.paginate). Items are
 * read from the endpoint's list_keys; `on_item` is called once per kept item (the node is
 * owned by the page and valid only during the callback; return non-zero to stop early).
 * `limit` <= 0 means no limit. `payload` (may be NULL) holds the endpoint's own fields.
 * The next window starts right after the last item received, not at EndNum + 1: every
 * endpoint caps a page (30 or 100 items) and truncates larger windows. */
servoom_status servoom_client_list(servoom_client *client, servoom_endpoint ep,
                                   const cJSON *payload, int limit,
                                   servoom_item_fn on_item, void *userdata);

/* Same, collected into a cJSON array the caller frees. */
servoom_status servoom_client_collect(servoom_client *client, servoom_endpoint ep,
                                      const cJSON *payload, int limit, cJSON **out_array);

/* The filter block every gallery listing takes (CLOUD_API.md "Gallery filters"):
 * Classify 0, FileSize (settings.file_size_filter), FileType 5, FileSort 0, Version 19,
 * RefreshIndex 0, then `extra` (may be NULL) merged over it. Caller frees. */
cJSON *servoom_client_filters(const servoom_client *client, const cJSON *extra);

/* ---- single-shot lookups (ReturnCode must be 0, else SERVOOM_ERR_API and *out == NULL) */
servoom_status servoom_client_gallery_info(servoom_client *client, int64_t gallery_id, cJSON **out);
servoom_status servoom_client_someone_info(servoom_client *client, int64_t user_id, cJSON **out);
servoom_status servoom_client_tag_info(servoom_client *client, const char *tag_name, cJSON **out);
/* UserList array (detached from the response; empty array if none). SearchUser has answered
 * ReturnCode 1 for every query since 2026-09-24 (server-side breakage). */
servoom_status servoom_client_search_user(servoom_client *client, const char *query, cJSON **out_list);
/* First page of Tag/SearchTagMoreV2 (fuzzy match; counts and 5 sample artworks per tag).
 * Use servoom_client_list_tags for more pages or a prefix match. */
servoom_status servoom_client_search_tag(servoom_client *client, const char *query, cJSON **out_list);

/* ---- paginated listings (`extra` may be NULL; it adds/overrides payload fields) ----- */
servoom_status servoom_client_list_my_uploads(servoom_client *c, int limit, const cJSON *extra,
                                              servoom_item_fn on_item, void *userdata);
servoom_status servoom_client_list_someone_uploads(servoom_client *c, int64_t user_id, int limit,
                                                   const cJSON *extra, servoom_item_fn on_item,
                                                   void *userdata);
servoom_status servoom_client_list_category(servoom_client *c, int category_id, int limit,
                                            const cJSON *extra, servoom_item_fn on_item,
                                            void *userdata);
servoom_status servoom_client_list_tag_gallery(servoom_client *c, const char *tag_name, int limit,
                                               const cJSON *extra, servoom_item_fn on_item,
                                               void *userdata);
servoom_status servoom_client_search_gallery(servoom_client *c, const char *query, int limit,
                                             const cJSON *extra, servoom_item_fn on_item,
                                             void *userdata);
servoom_status servoom_client_list_like_users(servoom_client *c, int64_t gallery_id, int limit,
                                              servoom_item_fn on_item, void *userdata);
/* Tags matching `query` (fuzzy); pass {"TagKey": "..."} in `extra` for a prefix match. */
servoom_status servoom_client_list_tags(servoom_client *c, const char *query, int limit,
                                        const cJSON *extra, servoom_item_fn on_item, void *userdata);

/* Convenience: collect a listing into a cJSON array (caller frees with cJSON_Delete). */
servoom_status servoom_client_collect_someone_uploads(servoom_client *c, int64_t user_id,
                                                      int limit, cJSON **out_array);

/* ---- artworks: comments and the server-side legacy render ------------------------ */
/* Top-level comments, newest first; replies nest under CommentChildList. */
servoom_status servoom_client_list_art_comments(servoom_client *c, int64_t gallery_id, int limit,
                                                servoom_item_fn on_item, void *userdata);
/* Cloud/GetFileData: the server decodes legacy 16x16 containers (and downsamples the old
 * 64x64 animations) into FileData (RGB bytes), PicCount, Speed. Modern files come back with
 * an empty FileData. Pass gallery_id > 0 or file_id. No token needed. */
servoom_status servoom_client_legacy_preview(servoom_client *c, int64_t gallery_id,
                                             const char *file_id, cJSON **out);

/* ---- users -------------------------------------------------------------------- */
servoom_status servoom_client_my_info(servoom_client *c, cJSON **out);
servoom_status servoom_client_user_score(servoom_client *c, int64_t user_id, cJSON **out);
/* MedalList array (all medals the app knows, IsValid/ValidTime per user). */
servoom_status servoom_client_user_medals(servoom_client *c, int64_t user_id, const char *language,
                                          cJSON **out_list);
/* Ranked artists; each record carries counters and 5 sample artworks in FileList. */
servoom_status servoom_client_list_experts(servoom_client *c, int limit, servoom_item_fn on_item,
                                           void *userdata);
/* ExpertList array: the ten artists featured on the Gallery tab. */
servoom_status servoom_client_hot_experts(servoom_client *c, cJSON **out_list);
servoom_status servoom_client_list_expert_gallery(servoom_client *c, int limit, const cJSON *extra,
                                                  servoom_item_fn on_item, void *userdata);
servoom_status servoom_client_list_tag_users(servoom_client *c, const char *tag_name, int limit,
                                             servoom_item_fn on_item, void *userdata);
/* Own account only: the server ignores any user id on these two. */
servoom_status servoom_client_list_my_followers(servoom_client *c, int limit, servoom_item_fn on_item,
                                                void *userdata);
servoom_status servoom_client_list_my_following(servoom_client *c, int limit, servoom_item_fn on_item,
                                                void *userdata);
servoom_status servoom_client_list_my_likes(servoom_client *c, int limit, const cJSON *extra,
                                            servoom_item_fn on_item, void *userdata);
servoom_status servoom_client_list_blacklist(servoom_client *c, int limit, servoom_item_fn on_item,
                                             void *userdata);

/* ---- tags and events ------------------------------------------------------------ */
/* TagList array of {TagName, GalleryCnt} starting with `prefix` (up to 30). */
servoom_status servoom_client_suggest_tags(servoom_client *c, const char *prefix, cJSON **out_list);
/* TagList array: the five trending tags. */
servoom_status servoom_client_hot_tags(servoom_client *c, const char *language, cJSON **out_list);
/* Name of the running contest (MatchKey) into `buf`; empty string when unavailable. */
servoom_status servoom_client_match_info(servoom_client *c, char *buf, size_t cap);

/* ---- discovery ------------------------------------------------------------------ */
servoom_status servoom_client_list_albums(servoom_client *c, int limit, const cJSON *extra,
                                          servoom_item_fn on_item, void *userdata);
servoom_status servoom_client_album_info(servoom_client *c, int64_t album_id, cJSON **out);
servoom_status servoom_client_list_album_arts(servoom_client *c, int64_t album_id, int limit,
                                              const cJSON *extra, servoom_item_fn on_item,
                                              void *userdata);
/* ThemeList array of {ForumId, ImageId, Title}. */
servoom_status servoom_client_discover_themes(servoom_client *c, cJSON **out_list);
servoom_status servoom_client_discover_top_new(servoom_client *c, cJSON **out);

/* ---- playlists ------------------------------------------------------------------ */
servoom_status servoom_client_list_user_playlists(servoom_client *c, int64_t user_id, int limit,
                                                  servoom_item_fn on_item, void *userdata);
servoom_status servoom_client_list_my_playlists(servoom_client *c, int limit, servoom_item_fn on_item,
                                                void *userdata);
/* `user_id` <= 0 reads one of the current account's playlists. */
servoom_status servoom_client_list_playlist_arts(servoom_client *c, int64_t user_id, int64_t play_id,
                                                 int limit, const cJSON *extra,
                                                 servoom_item_fn on_item, void *userdata);

/* ---- forum: the official article feed (FORUM_API.md) ------------------------------ */
/* TagList array of {TagValue, TagName}. */
servoom_status servoom_client_forum_tags(servoom_client *c, servoom_forum_region region,
                                         cJSON **out_list);
/* Posts newest first. `tag` < 0 means no tag filter (a TagValue from forum_tags otherwise;
 * the curated block on page 1 ignores it, so it is also enforced client-side). `dedupe`
 * drops ForumIds repeated by that curated block. */
servoom_status servoom_client_list_forum_posts(servoom_client *c, servoom_forum_region region,
                                               int tag, int dedupe, int limit,
                                               servoom_item_fn on_item, void *userdata);
/* The fixed "Pixel Art Ambassador Program" post (the endpoint ignores every id). */
servoom_status servoom_client_forum_ambassador_post(servoom_client *c, cJSON **out);
/* Top-level comments on a forum post, newest first; replies under CommentChildList. */
servoom_status servoom_client_list_forum_comments(servoom_client *c, int64_t forum_id,
                                                  servoom_forum_region region, int limit,
                                                  servoom_item_fn on_item, void *userdata);

/* ---- notification inbox, chats, letters, chat-room directory ---------------------- */
servoom_status servoom_client_unread_counts(servoom_client *c, cJSON **out);
servoom_status servoom_client_notify_config(servoom_client *c, cJSON **out);
servoom_status servoom_client_list_like_notifications(servoom_client *c, int limit,
                                                      servoom_item_fn on_item, void *userdata);
servoom_status servoom_client_list_comment_notifications(servoom_client *c, int limit,
                                                         servoom_item_fn on_item, void *userdata);
servoom_status servoom_client_list_follower_notifications(servoom_client *c, int limit,
                                                          servoom_item_fn on_item, void *userdata);
/* ConversationList array of {TargetUserId, Message, SendTime}. */
servoom_status servoom_client_conversations(servoom_client *c, cJSON **out_list);
servoom_status servoom_client_list_letters(servoom_client *c, int limit, servoom_item_fn on_item,
                                           void *userdata);
/* Community chat rooms flattened into one array; each record gains "ClassifyName". Only the
 * directory is served here; the messages go through the IM provider (FORUM_API.md). */
servoom_status servoom_client_chat_groups(servoom_client *c, cJSON **out_list);

/* ---- downloads -------------------------------------------------------------------- */

/* Download any cloud file (an artwork FileId or a LayerFileId). No login needed. */
servoom_status servoom_client_download_file(servoom_client *client, const char *file_id,
                                            const char *output_path);
servoom_status servoom_client_download_memory(servoom_client *client, const char *file_id,
                                              uint8_t **out_data, size_t *out_len);

/* Fetch gallery metadata, then download its artwork file into `output_dir` as
 * "<gallery_id>_<sanitized FileName>.dat" (Python naming). `out_path` receives a malloc'd
 * path the caller frees. `out_info` (optional) receives the GalleryInfo response. */
servoom_status servoom_client_download_artwork(servoom_client *client, int64_t gallery_id,
                                               const char *output_dir, char **out_path,
                                               cJSON **out_info);

/* Sanitize a file name for Windows/Unix (same rules as servoom.util.sanitize_filename);
 * writes at most `cap-1` chars + NUL. */
void servoom_sanitize_filename(const char *name, char *out, size_t cap);

#ifdef __cplusplus
}
#endif
#endif
