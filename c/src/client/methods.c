/* Named wrappers over the endpoint table: one per DivoomClient method (forum, inbox,
 * users, tags, discovery, playlists). Built only from the public generic calls. */
#include "servoom/client.h"

#include <stdio.h>
#include <string.h>

/* ---- small payload helpers ------------------------------------------------ */

static cJSON *obj(void)
{
    return cJSON_CreateObject();
}

static cJSON *with_num(cJSON *p, const char *key, double v)
{
    if (p)
        cJSON_AddNumberToObject(p, key, v);
    return p;
}

static cJSON *with_str(cJSON *p, const char *key, const char *v)
{
    if (p)
        cJSON_AddStringToObject(p, key, v ? v : "");
    return p;
}

static cJSON *with_extra(cJSON *p, const cJSON *extra)
{
    const cJSON *item;
    if (!p || !extra)
        return p;
    cJSON_ArrayForEach(item, extra) {
        if (!item->string)
            continue;
        cJSON *dup = cJSON_Duplicate(item, 1);
        if (!dup) {
            cJSON_Delete(p);
            return NULL;
        }
        cJSON_DeleteItemFromObjectCaseSensitive(p, item->string);
        cJSON_AddItemToObject(p, item->string, dup);
    }
    return p;
}

/* lookup() then detach `key` as an array (empty array on API error, like Python's
 * (resp or {}).get(key, [])). */
static servoom_status lookup_list(servoom_client *c, servoom_endpoint ep, cJSON *payload,
                                  const char *key, cJSON **out_list)
{
    if (!c || !out_list)
        return SERVOOM_ERR_ARG;
    *out_list = NULL;
    if (!payload)
        return SERVOOM_ERR_NOMEM;
    cJSON *resp = NULL;
    servoom_status st = servoom_client_lookup(c, ep, payload, &resp);
    cJSON_Delete(payload);
    if (st == SERVOOM_ERR_API) {
        *out_list = cJSON_CreateArray();
        return *out_list ? SERVOOM_OK : SERVOOM_ERR_NOMEM;
    }
    if (st != SERVOOM_OK)
        return st;
    cJSON *list = cJSON_DetachItemFromObjectCaseSensitive(resp, key);
    cJSON_Delete(resp);
    if (!list || !cJSON_IsArray(list)) {
        cJSON_Delete(list);
        list = cJSON_CreateArray();
    }
    *out_list = list;
    return list ? SERVOOM_OK : SERVOOM_ERR_NOMEM;
}

static servoom_status lookup_obj(servoom_client *c, servoom_endpoint ep, cJSON *payload, cJSON **out)
{
    if (!c || !out)
        return SERVOOM_ERR_ARG;
    *out = NULL;
    if (!payload)
        return SERVOOM_ERR_NOMEM;
    servoom_status st = servoom_client_lookup(c, ep, payload, out);
    cJSON_Delete(payload);
    return st;
}

static servoom_status list_with(servoom_client *c, servoom_endpoint ep, cJSON *payload, int limit,
                                servoom_item_fn on_item, void *ud)
{
    if (!c)
        return SERVOOM_ERR_ARG;
    if (!payload)
        return SERVOOM_ERR_NOMEM;
    servoom_status st = servoom_client_list(c, ep, payload, limit, on_item, ud);
    cJSON_Delete(payload);
    return st;
}

/* ---- artworks ------------------------------------------------------------- */

servoom_status servoom_client_list_art_comments(servoom_client *c, int64_t gallery_id, int limit,
                                                servoom_item_fn on_item, void *ud)
{
    return list_with(c, SERVOOM_EP_ART_COMMENTS, with_num(obj(), "GalleryId", (double)gallery_id),
                     limit, on_item, ud);
}

servoom_status servoom_client_legacy_preview(servoom_client *c, int64_t gallery_id, const char *file_id,
                                             cJSON **out)
{
    if (gallery_id <= 0 && (!file_id || !*file_id))
        return SERVOOM_ERR_ARG;
    cJSON *p = gallery_id > 0 ? with_num(obj(), "GalleryId", (double)gallery_id)
                              : with_str(obj(), "FileId", file_id);
    return lookup_obj(c, SERVOOM_EP_LEGACY_PREVIEW, p, out);
}

/* ---- users ---------------------------------------------------------------- */

servoom_status servoom_client_my_info(servoom_client *c, cJSON **out)
{
    return lookup_obj(c, SERVOOM_EP_USER_ALL_INFO, obj(), out);
}

servoom_status servoom_client_user_score(servoom_client *c, int64_t user_id, cJSON **out)
{
    return lookup_obj(c, SERVOOM_EP_USER_SCORE, with_num(obj(), "TargetUserId", (double)user_id), out);
}

servoom_status servoom_client_user_medals(servoom_client *c, int64_t user_id, const char *language,
                                          cJSON **out_list)
{
    cJSON *p = with_str(with_num(obj(), "TargetUserId", (double)user_id), "Langue", language ? language : "en");
    return lookup_list(c, SERVOOM_EP_USER_MEDALS, p, "MedalList", out_list);
}

servoom_status servoom_client_list_experts(servoom_client *c, int limit, servoom_item_fn on_item, void *ud)
{
    if (!c)
        return SERVOOM_ERR_ARG;
    cJSON *p = servoom_client_filters(c, NULL);
    if (p) {
        cJSON_DeleteItemFromObjectCaseSensitive(p, "Classify");
        cJSON_DeleteItemFromObjectCaseSensitive(p, "FileSort");
        cJSON_AddStringToObject(p, "Language", "en");
    }
    return list_with(c, SERVOOM_EP_EXPERTS, p, limit, on_item, ud);
}

servoom_status servoom_client_hot_experts(servoom_client *c, cJSON **out_list)
{
    return lookup_list(c, SERVOOM_EP_HOT_EXPERTS, obj(), "ExpertList", out_list);
}

servoom_status servoom_client_list_expert_gallery(servoom_client *c, int limit, const cJSON *extra,
                                                  servoom_item_fn on_item, void *ud)
{
    return list_with(c, SERVOOM_EP_EXPERT_GALLERY, with_extra(obj(), extra), limit, on_item, ud);
}

servoom_status servoom_client_list_tag_users(servoom_client *c, const char *tag_name, int limit,
                                             servoom_item_fn on_item, void *ud)
{
    if (!tag_name)
        return SERVOOM_ERR_ARG;
    return list_with(c, SERVOOM_EP_TAG_USERS, with_str(with_str(obj(), "TagName", tag_name), "Language", "en"),
                     limit, on_item, ud);
}

servoom_status servoom_client_list_my_followers(servoom_client *c, int limit, servoom_item_fn on_item, void *ud)
{
    return list_with(c, SERVOOM_EP_MY_FOLLOWERS, obj(), limit, on_item, ud);
}

servoom_status servoom_client_list_my_following(servoom_client *c, int limit, servoom_item_fn on_item, void *ud)
{
    return list_with(c, SERVOOM_EP_MY_FOLLOWING, obj(), limit, on_item, ud);
}

servoom_status servoom_client_list_my_likes(servoom_client *c, int limit, const cJSON *extra,
                                            servoom_item_fn on_item, void *ud)
{
    if (!c)
        return SERVOOM_ERR_ARG;
    return list_with(c, SERVOOM_EP_MY_LIKES, servoom_client_filters(c, extra), limit, on_item, ud);
}

servoom_status servoom_client_list_blacklist(servoom_client *c, int limit, servoom_item_fn on_item, void *ud)
{
    return list_with(c, SERVOOM_EP_BLACKLIST, obj(), limit, on_item, ud);
}

/* ---- tags and events ------------------------------------------------------ */

servoom_status servoom_client_suggest_tags(servoom_client *c, const char *prefix, cJSON **out_list)
{
    if (!prefix)
        return SERVOOM_ERR_ARG;
    return lookup_list(c, SERVOOM_EP_SUGGEST_TAG, with_str(obj(), "TagKey", prefix), "TagList", out_list);
}

servoom_status servoom_client_hot_tags(servoom_client *c, const char *language, cJSON **out_list)
{
    return lookup_list(c, SERVOOM_EP_HOT_TAGS, with_str(obj(), "Language", language ? language : "en"),
                       "TagList", out_list);
}

servoom_status servoom_client_match_info(servoom_client *c, char *buf, size_t cap)
{
    if (!c || !buf || cap == 0)
        return SERVOOM_ERR_ARG;
    buf[0] = 0;
    cJSON *resp = NULL;
    servoom_status st = lookup_obj(c, SERVOOM_EP_MATCH_INFO, obj(), &resp);
    if (st != SERVOOM_OK)
        return st;
    const cJSON *k = cJSON_GetObjectItemCaseSensitive(resp, "MatchKey");
    if (cJSON_IsString(k))
        snprintf(buf, cap, "%s", k->valuestring);
    cJSON_Delete(resp);
    return SERVOOM_OK;
}

/* ---- discovery ------------------------------------------------------------ */

servoom_status servoom_client_list_albums(servoom_client *c, int limit, const cJSON *extra,
                                          servoom_item_fn on_item, void *ud)
{
    if (!c)
        return SERVOOM_ERR_ARG;
    cJSON *p = servoom_client_filters(c, NULL);
    if (p) {
        cJSON_DeleteItemFromObjectCaseSensitive(p, "Classify");
        cJSON_DeleteItemFromObjectCaseSensitive(p, "FileType");
        cJSON_DeleteItemFromObjectCaseSensitive(p, "Version");
        cJSON_DeleteItemFromObjectCaseSensitive(p, "RefreshIndex");
    }
    return list_with(c, SERVOOM_EP_ALBUMS, with_extra(p, extra), limit, on_item, ud);
}

servoom_status servoom_client_album_info(servoom_client *c, int64_t album_id, cJSON **out)
{
    cJSON *p = with_str(with_str(with_num(obj(), "AlbumId", (double)album_id), "Langue", "en"), "CountryISOCode", "US");
    return lookup_obj(c, SERVOOM_EP_ALBUM_INFO, p, out);
}

servoom_status servoom_client_list_album_arts(servoom_client *c, int64_t album_id, int limit,
                                              const cJSON *extra, servoom_item_fn on_item, void *ud)
{
    if (!c)
        return SERVOOM_ERR_ARG;
    cJSON *p = with_num(servoom_client_filters(c, extra), "AlbumId", (double)album_id);
    return list_with(c, SERVOOM_EP_ALBUM_ARTS, p, limit, on_item, ud);
}

servoom_status servoom_client_discover_themes(servoom_client *c, cJSON **out_list)
{
    return lookup_list(c, SERVOOM_EP_DISCOVER_THEMES, obj(), "ThemeList", out_list);
}

servoom_status servoom_client_discover_top_new(servoom_client *c, cJSON **out)
{
    return lookup_obj(c, SERVOOM_EP_DISCOVER_TOP_NEW, obj(), out);
}

/* ---- playlists ------------------------------------------------------------ */

servoom_status servoom_client_list_user_playlists(servoom_client *c, int64_t user_id, int limit,
                                                  servoom_item_fn on_item, void *ud)
{
    cJSON *p = with_str(with_num(obj(), "TargetUserId", (double)user_id), "Language", "en");
    return list_with(c, SERVOOM_EP_USER_PLAYLISTS, p, limit, on_item, ud);
}

servoom_status servoom_client_list_my_playlists(servoom_client *c, int limit, servoom_item_fn on_item, void *ud)
{
    return list_with(c, SERVOOM_EP_MY_PLAYLISTS, obj(), limit, on_item, ud);
}

servoom_status servoom_client_list_playlist_arts(servoom_client *c, int64_t user_id, int64_t play_id, int limit,
                                                 const cJSON *extra, servoom_item_fn on_item, void *ud)
{
    if (!c)
        return SERVOOM_ERR_ARG;
    cJSON *p = with_num(servoom_client_filters(c, extra), "PlayId", (double)play_id);
    if (user_id > 0)
        return list_with(c, SERVOOM_EP_USER_PLAYLIST_ARTS, with_num(p, "TargetUserId", (double)user_id),
                         limit, on_item, ud);
    return list_with(c, SERVOOM_EP_MY_PLAYLIST_ARTS, p, limit, on_item, ud);
}

/* ---- forum ---------------------------------------------------------------- */

servoom_status servoom_client_forum_tags(servoom_client *c, servoom_forum_region region, cJSON **out_list)
{
    return lookup_list(c, SERVOOM_EP_FORUM_TAGS, with_num(obj(), "RegionId", (double)region), "TagList", out_list);
}

struct forum_filter {
    int tag;
    int dedupe;
    servoom_item_fn on_item;
    void *ud;
    cJSON *seen; /* array of ForumId strings */
    int limit;   /* counted here, because filtered-out items must not count */
    int count;
};

static int forum_keep(const cJSON *item, void *ud)
{
    struct forum_filter *f = (struct forum_filter *)ud;
    char idbuf[64] = "";
    if (f->tag >= 0) {
        const cJSON *t = cJSON_GetObjectItemCaseSensitive(item, "TagID");
        char tbuf[32];
        if (cJSON_IsNumber(t))
            snprintf(tbuf, sizeof tbuf, "%.0f", t->valuedouble);
        else
            snprintf(tbuf, sizeof tbuf, "%s", cJSON_IsString(t) ? t->valuestring : "");
        char want[32];
        snprintf(want, sizeof want, "%d", f->tag);
        if (strcmp(tbuf, want) != 0)
            return 0;
    }
    if (f->dedupe) {
        const cJSON *id = cJSON_GetObjectItemCaseSensitive(item, "ForumId");
        if (cJSON_IsNumber(id))
            snprintf(idbuf, sizeof idbuf, "%.0f", id->valuedouble);
        else if (cJSON_IsString(id))
            snprintf(idbuf, sizeof idbuf, "%s", id->valuestring);
        const cJSON *s;
        cJSON_ArrayForEach(s, f->seen) {
            if (cJSON_IsString(s) && strcmp(s->valuestring, idbuf) == 0)
                return 0;
        }
        cJSON_AddItemToArray(f->seen, cJSON_CreateString(idbuf));
    }
    if (f->on_item && f->on_item(item, f->ud) != 0)
        return 1;
    f->count++;
    return (f->limit > 0 && f->count >= f->limit) ? 1 : 0;
}

servoom_status servoom_client_list_forum_posts(servoom_client *c, servoom_forum_region region, int tag,
                                               int dedupe, int limit, servoom_item_fn on_item, void *ud)
{
    if (!c)
        return SERVOOM_ERR_ARG;
    cJSON *p = with_num(obj(), "RegionId", (double)region);
    if (p && tag >= 0) {
        char buf[32];
        snprintf(buf, sizeof buf, "%d", tag);
        cJSON_AddStringToObject(p, "Tag", buf);
    }
    struct forum_filter f = {tag, dedupe, on_item, ud, cJSON_CreateArray(), limit, 0};
    if (!p || !f.seen) {
        cJSON_Delete(p);
        cJSON_Delete(f.seen);
        return SERVOOM_ERR_NOMEM;
    }
    /* Filtered-out items must not count towards `limit`, so the filter counts kept items
     * itself and stops the lister; the lister runs unlimited. */
    servoom_status st = servoom_client_list(c, SERVOOM_EP_FORUM_LIST, p, 0, forum_keep, &f);
    cJSON_Delete(p);
    cJSON_Delete(f.seen);
    return st;
}

servoom_status servoom_client_forum_ambassador_post(servoom_client *c, cJSON **out)
{
    return lookup_obj(c, SERVOOM_EP_FORUM_AMBASSADOR_POST, obj(), out);
}

servoom_status servoom_client_list_forum_comments(servoom_client *c, int64_t forum_id, servoom_forum_region region,
                                                  int limit, servoom_item_fn on_item, void *ud)
{
    char buf[32];
    snprintf(buf, sizeof buf, "%lld", (long long)forum_id);
    cJSON *p = with_str(with_num(obj(), "RegionId", (double)region), "ForumId", buf);
    return list_with(c, SERVOOM_EP_FORUM_COMMENTS, p, limit, on_item, ud);
}

/* ---- inbox ---------------------------------------------------------------- */

servoom_status servoom_client_unread_counts(servoom_client *c, cJSON **out)
{
    return lookup_obj(c, SERVOOM_EP_MESSAGE_UNREAD_CNT, obj(), out);
}

servoom_status servoom_client_notify_config(servoom_client *c, cJSON **out)
{
    return lookup_obj(c, SERVOOM_EP_MESSAGE_NOTIFY_CONFIG, obj(), out);
}

servoom_status servoom_client_list_like_notifications(servoom_client *c, int limit, servoom_item_fn on_item, void *ud)
{
    return list_with(c, SERVOOM_EP_MESSAGE_LIKE_LIST, obj(), limit, on_item, ud);
}

servoom_status servoom_client_list_comment_notifications(servoom_client *c, int limit, servoom_item_fn on_item,
                                                         void *ud)
{
    return list_with(c, SERVOOM_EP_MESSAGE_COMMENT_LIST, obj(), limit, on_item, ud);
}

servoom_status servoom_client_list_follower_notifications(servoom_client *c, int limit, servoom_item_fn on_item,
                                                          void *ud)
{
    return list_with(c, SERVOOM_EP_MESSAGE_FANS_LIST, obj(), limit, on_item, ud);
}

servoom_status servoom_client_conversations(servoom_client *c, cJSON **out_list)
{
    return lookup_list(c, SERVOOM_EP_MESSAGE_CONVERSATIONS, obj(), "ConversationList", out_list);
}

servoom_status servoom_client_list_letters(servoom_client *c, int limit, servoom_item_fn on_item, void *ud)
{
    return list_with(c, SERVOOM_EP_MESSAGE_LETTERS, obj(), limit, on_item, ud);
}

servoom_status servoom_client_chat_groups(servoom_client *c, cJSON **out_list)
{
    if (!c || !out_list)
        return SERVOOM_ERR_ARG;
    *out_list = NULL;
    cJSON *resp = NULL;
    servoom_status st = lookup_obj(c, SERVOOM_EP_MESSAGE_GROUP_LIST, obj(), &resp);
    cJSON *groups = cJSON_CreateArray();
    if (!groups) {
        cJSON_Delete(resp);
        return SERVOOM_ERR_NOMEM;
    }
    if (st == SERVOOM_OK) {
        const cJSON *classify;
        cJSON_ArrayForEach(classify, cJSON_GetObjectItemCaseSensitive(resp, "ClassifyList")) {
            const cJSON *name = cJSON_GetObjectItemCaseSensitive(classify, "ClassifyName");
            const cJSON *g;
            cJSON_ArrayForEach(g, cJSON_GetObjectItemCaseSensitive(classify, "GroupList")) {
                cJSON *dup = cJSON_Duplicate(g, 1);
                if (!dup)
                    continue;
                cJSON_DeleteItemFromObjectCaseSensitive(dup, "ClassifyName");
                cJSON_AddStringToObject(dup, "ClassifyName", cJSON_IsString(name) ? name->valuestring : "");
                cJSON_AddItemToArray(groups, dup);
            }
        }
    } else if (st != SERVOOM_ERR_API) {
        cJSON_Delete(groups);
        cJSON_Delete(resp);
        return st;
    }
    cJSON_Delete(resp);
    *out_list = groups;
    return SERVOOM_OK;
}
