/* Live cloud-client test. Needs SERVOOM_EMAIL and SERVOOM_PASSWORD (or
 * SERVOOM_MD5_PASSWORD) in the environment; otherwise it is skipped (exit 77).
 *
 * Part 1 runs anonymously (no credentials): the endpoints CLOUD_API.md lists as
 * token-free must answer, and the page-cap behaviour of the category feed is checked.
 * Part 2 logs in, lists the account's own uploads, pages a public category feed, fetches
 * gallery info for the first item, downloads its artwork file and decodes it, then touches
 * the forum, inbox, tag, playlist and discovery calls. No particular artwork or user is
 * hard-coded beyond what the feeds return. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "servoom/servoom.h"
#include "testlib.h"

static int count_items(const cJSON *item, void *ud)
{
    int *n = (int *)ud;
    (*n)++;
    CHECK(cJSON_IsObject(item), "item is an object");
    return 0;
}

static int count_gallery_items(const cJSON *item, void *ud)
{
    int *n = (int *)ud;
    (*n)++;
    CHECK(cJSON_IsObject(item) && cJSON_GetObjectItemCaseSensitive(item, "GalleryId"), "item has GalleryId");
    return 0;
}

static int first_gallery(const cJSON *item, void *ud)
{
    const cJSON *gid = cJSON_GetObjectItemCaseSensitive(item, "GalleryId");
    if (cJSON_IsNumber(gid)) {
        *(int64_t *)ud = (int64_t)gid->valuedouble;
        return 1; /* stop after the first */
    }
    return 0;
}

static int first_number(const cJSON *item, const char *key, int64_t *out)
{
    const cJSON *v = cJSON_GetObjectItemCaseSensitive(item, key);
    if (cJSON_IsNumber(v)) {
        *out = (int64_t)v->valuedouble;
        return 1;
    }
    if (cJSON_IsString(v)) {
        *out = atoll(v->valuestring);
        return 1;
    }
    return 0;
}

struct id_grab {
    const char *key;
    int64_t id;
};

static int grab_first_id(const cJSON *item, void *ud)
{
    struct id_grab *g = (struct id_grab *)ud;
    return first_number(item, g->key, &g->id) ? 1 : 0;
}

/* Collect GalleryIds into a fixed array (for the page-cap check). */
struct id_list {
    int64_t ids[256];
    int n;
};

static int collect_ids(const cJSON *item, void *ud)
{
    struct id_list *l = (struct id_list *)ud;
    int64_t id;
    if (l->n < 256 && first_number(item, "GalleryId", &id))
        l->ids[l->n++] = id;
    return 0;
}

static void anonymous_part(void)
{
    servoom_client_settings s;
    servoom_client_settings_default(&s);
    s.batch_size = 40; /* larger than the 30-item cap of the category feed */
    servoom_client *a = servoom_client_new_anonymous(&s);
    if (!CHECK(a != NULL, "anonymous client alloc"))
        return;
    CHECK(servoom_client_is_anonymous(a) && !servoom_client_is_logged_in(a), "anonymous state");
    CHECK(servoom_client_login(a) == SERVOOM_ERR_STATE, "anonymous login refused");

    /* 70 newest items with a 40-item window: the server truncates each window to 30, so
     * advancing by items received must yield 70 distinct ids without gaps or repeats. */
    struct id_list l = {{0}, 0};
    servoom_status st = servoom_client_list_category(a, SERVOOM_CAT_NEW, 70, NULL, collect_ids, &l);
    CHECK(st == SERVOOM_OK && l.n == 70, "anonymous category listing 70 items across capped pages: %s, n=%d",
          servoom_status_str(st), l.n);
    int dup = 0;
    for (int i = 0; i < l.n; i++)
        for (int j = i + 1; j < l.n; j++)
            if (l.ids[i] == l.ids[j])
                dup++;
    CHECK(dup == 0, "no repeated GalleryId across pages (dup=%d)", dup);

    int n = 0;
    st = servoom_client_list_experts(a, 35, count_items, &n);
    CHECK(st == SERVOOM_OK && n == 35, "experts listing (cap 30 per page): %s, n=%d", servoom_status_str(st), n);

    cJSON *hot = NULL;
    st = servoom_client_hot_experts(a, &hot);
    CHECK(st == SERVOOM_OK && hot && cJSON_GetArraySize(hot) > 0, "hot experts: %s", servoom_status_str(st));
    int64_t uid = 0;
    if (hot && cJSON_GetArraySize(hot) > 0)
        first_number(cJSON_GetArrayItem(hot, 0), "ExpertUserId", &uid);
    cJSON_Delete(hot);

    if (uid > 0) {
        cJSON *info = NULL;
        st = servoom_client_someone_info(a, uid, &info);
        CHECK(st == SERVOOM_OK && info && cJSON_GetObjectItemCaseSensitive(info, "NickName"), "anonymous profile: %s",
              servoom_status_str(st));
        cJSON_Delete(info);
        cJSON *medals = NULL;
        st = servoom_client_user_medals(a, uid, "en", &medals);
        CHECK(st == SERVOOM_OK && medals && cJSON_GetArraySize(medals) > 0, "medals: %s", servoom_status_str(st));
        cJSON_Delete(medals);
        cJSON *score = NULL;
        st = servoom_client_user_score(a, uid, &score);
        CHECK(st == SERVOOM_OK && score && cJSON_GetObjectItemCaseSensitive(score, "Score"), "score: %s",
              servoom_status_str(st));
        cJSON_Delete(score);
        n = 0;
        st = servoom_client_list_someone_uploads(a, uid, 5, NULL, count_gallery_items, &n);
        CHECK(st == SERVOOM_OK && n == 5, "anonymous someone uploads: %s, n=%d", servoom_status_str(st), n);
    }

    n = 0;
    st = servoom_client_search_gallery(a, "cat", 45, NULL, count_gallery_items, &n);
    CHECK(st == SERVOOM_OK && n == 45, "anonymous search with the filter block: %s, n=%d", servoom_status_str(st), n);

    struct id_grab album = {"AlbumId", 0};
    st = servoom_client_list_albums(a, 3, NULL, grab_first_id, &album);
    CHECK(st == SERVOOM_OK && album.id > 0, "albums: %s", servoom_status_str(st));
    if (album.id > 0) {
        n = 0;
        st = servoom_client_list_album_arts(a, album.id, 5, NULL, count_gallery_items, &n);
        CHECK(st == SERVOOM_OK && n == 5, "album arts: %s, n=%d", servoom_status_str(st), n);
        cJSON *ai = NULL;
        st = servoom_client_album_info(a, album.id, &ai);
        CHECK(st == SERVOOM_OK && ai && cJSON_GetObjectItemCaseSensitive(ai, "LikeCnt"), "album info: %s",
              servoom_status_str(st));
        cJSON_Delete(ai);
    }

    char match[64];
    st = servoom_client_match_info(a, match, sizeof match);
    CHECK(st == SERVOOM_OK && match[0], "match info: %s (%s)", servoom_status_str(st), match);

    cJSON *tags = NULL;
    st = servoom_client_search_tag(a, "cat", &tags);
    CHECK(st == SERVOOM_OK && tags && cJSON_GetArraySize(tags) > 0, "tag search first page: %s", servoom_status_str(st));
    cJSON_Delete(tags);

    n = 0;
    st = servoom_client_list_forum_posts(a, SERVOOM_REGION_INTERNATIONAL, -1, 1, 12, count_items, &n);
    CHECK(st == SERVOOM_OK && n == 12, "anonymous forum posts: %s, n=%d", servoom_status_str(st), n);

    /* A token-only endpoint answers ReturnCode 11 anonymously. */
    cJSON *ti = NULL;
    st = servoom_client_tag_info(a, "cat", &ti);
    CHECK(st == SERVOOM_ERR_API && ti == NULL, "tag info needs a token (%s)", servoom_status_str(st));
    servoom_client_free(a);
}

int main(void)
{
#if !SERVOOM_WITH_CLIENT
    printf("built without the client -- skipping\n");
    return TL_SKIP;
#else
    const char *email = getenv("SERVOOM_EMAIL");
    const char *md5 = getenv("SERVOOM_MD5_PASSWORD");
    const char *plain = getenv("SERVOOM_PASSWORD");
    char md5buf[33];
    if (!email || !*email || (!(md5 && *md5) && !(plain && *plain))) {
        printf("SERVOOM_EMAIL / SERVOOM_PASSWORD not set -- skipping live test\n");
        return TL_SKIP;
    }
    if (!(md5 && *md5)) {
        servoom_md5_hex(plain, strlen(plain), md5buf);
        md5 = md5buf;
    }

    anonymous_part();

    servoom_client *c = servoom_client_new(email, md5, NULL);
    if (!CHECK(c != NULL, "client alloc"))
        return 1;
    servoom_status st = servoom_client_login(c);
    if (!CHECK(st == SERVOOM_OK, "login: %s (%s)", servoom_status_str(st), servoom_client_last_error(c))) {
        servoom_client_free(c);
        return tl_finish("test_live");
    }
    CHECK(servoom_client_is_logged_in(c) && servoom_client_user_id(c) > 0 && servoom_client_token(c),
          "login state");

    /* Own uploads: the account may have none; the call itself must succeed. */
    int mine = 0;
    st = servoom_client_list_my_uploads(c, 5, NULL, count_gallery_items, &mine);
    CHECK(st == SERVOOM_OK, "my uploads listing: %s (%s)", servoom_status_str(st), servoom_client_last_error(c));

    /* Public feed ("New" category), limited. */
    int n = 0;
    st = servoom_client_list_category(c, 0, 5, NULL, count_gallery_items, &n);
    CHECK(st == SERVOOM_OK && n == 5, "category listing limit 5: %s, n=%d", servoom_status_str(st), n);

    int64_t gallery_id = 0;
    st = servoom_client_list_category(c, 0, 1, NULL, first_gallery, &gallery_id);
    CHECK(st == SERVOOM_OK && gallery_id > 0, "pick a gallery id from the feed");

    cJSON *bad = NULL;
    st = servoom_client_gallery_info(c, 1, &bad);
    CHECK(st == SERVOOM_ERR_API && bad == NULL, "bogus gallery id -> api error (%s)", servoom_status_str(st));

    cJSON *info = NULL;
    st = servoom_client_gallery_info(c, gallery_id, &info);
    if (CHECK(st == SERVOOM_OK && info, "gallery info: %s", servoom_status_str(st))) {
        const cJSON *fid = cJSON_GetObjectItemCaseSensitive(info, "FileId");
        CHECK(cJSON_IsString(fid) && strlen(fid->valuestring) > 10, "FileId present");
        cJSON_Delete(info);
    }

    char *path = NULL;
    st = servoom_client_download_artwork(c, gallery_id, "live-test-downloads", &path, NULL);
    if (CHECK(st == SERVOOM_OK && path, "download artwork: %s (%s)", servoom_status_str(st),
              servoom_client_last_error(c))) {
        servoom_pixel_bean *bean = NULL;
        st = servoom_decode_file(path, &bean);
        if (CHECK(st == SERVOOM_OK, "decode downloaded artwork: %s", servoom_status_str(st))) {
            CHECK(bean->total_frames > 0 && bean->width > 0 && bean->height > 0 &&
                      servoom_format_is_artwork(bean->format),
                  "decoded artwork is sane (%d frames %dx%d, format %d)", bean->total_frames, bean->width,
                  bean->height, bean->format);
            servoom_pixel_bean_free(bean);
        }
        remove(path);
        free(path);
    }

    /* Token-only endpoints. */
    cJSON *me = NULL;
    st = servoom_client_my_info(c, &me);
    CHECK(st == SERVOOM_OK && me && cJSON_GetObjectItemCaseSensitive(me, "Email"), "my info: %s", servoom_status_str(st));
    cJSON_Delete(me);

    cJSON *ti = NULL;
    st = servoom_client_tag_info(c, "cat", &ti);
    CHECK(st == SERVOOM_OK && ti && cJSON_GetObjectItemCaseSensitive(ti, "GalleryCnt"), "tag info: %s",
          servoom_status_str(st));
    cJSON_Delete(ti);
    n = 0;
    st = servoom_client_list_tag_gallery(c, "cat", 35, NULL, count_gallery_items, &n);
    CHECK(st == SERVOOM_OK && n == 35, "tag gallery (cap 29-30 per page): %s, n=%d", servoom_status_str(st), n);
    n = 0;
    st = servoom_client_list_tag_users(c, "cat", 35, count_items, &n);
    CHECK(st == SERVOOM_OK && n == 35, "tag users: %s, n=%d", servoom_status_str(st), n);
    cJSON *sug = NULL;
    st = servoom_client_suggest_tags(c, "ca", &sug);
    CHECK(st == SERVOOM_OK && sug && cJSON_GetArraySize(sug) > 0, "tag suggestions: %s", servoom_status_str(st));
    cJSON_Delete(sug);
    cJSON *hott = NULL;
    st = servoom_client_hot_tags(c, "en", &hott);
    CHECK(st == SERVOOM_OK && hott && cJSON_GetArraySize(hott) == 5, "hot tags: %s", servoom_status_str(st));
    cJSON_Delete(hott);

    n = 0;
    st = servoom_client_list_like_users(c, gallery_id, 3, count_items, &n);
    CHECK(st == SERVOOM_OK, "like users: %s", servoom_status_str(st));
    n = 0;
    st = servoom_client_list_art_comments(c, gallery_id, 3, count_items, &n);
    CHECK(st == SERVOOM_OK, "art comments: %s", servoom_status_str(st));

    cJSON *themes = NULL;
    st = servoom_client_discover_themes(c, &themes);
    CHECK(st == SERVOOM_OK && themes && cJSON_GetArraySize(themes) > 0, "discover themes: %s", servoom_status_str(st));
    cJSON_Delete(themes);
    cJSON *top = NULL;
    st = servoom_client_discover_top_new(c, &top);
    CHECK(st == SERVOOM_OK && top && cJSON_GetObjectItemCaseSensitive(top, "NewList"), "discover top new: %s",
          servoom_status_str(st));
    cJSON_Delete(top);

    /* Forum: tags, posts with a tag filter, comments of the first post. */
    cJSON *ftags = NULL;
    st = servoom_client_forum_tags(c, SERVOOM_REGION_INTERNATIONAL, &ftags);
    CHECK(st == SERVOOM_OK && ftags && cJSON_GetArraySize(ftags) > 0, "forum tags: %s", servoom_status_str(st));
    int64_t tagv = -1;
    if (ftags && cJSON_GetArraySize(ftags) > 0)
        first_number(cJSON_GetArrayItem(ftags, 0), "TagValue", &tagv);
    cJSON_Delete(ftags);
    struct id_grab post = {"ForumId", 0};
    st = servoom_client_list_forum_posts(c, SERVOOM_REGION_INTERNATIONAL, (int)tagv, 1, 5, grab_first_id, &post);
    CHECK(st == SERVOOM_OK && post.id > 0, "forum posts with tag %lld: %s", (long long)tagv, servoom_status_str(st));
    if (post.id > 0) {
        n = 0;
        st = servoom_client_list_forum_comments(c, post.id, SERVOOM_REGION_INTERNATIONAL, 3, count_items, &n);
        CHECK(st == SERVOOM_OK, "forum comments: %s", servoom_status_str(st));
    }
    cJSON *amb = NULL;
    st = servoom_client_forum_ambassador_post(c, &amb);
    CHECK(st == SERVOOM_OK && amb && cJSON_GetObjectItemCaseSensitive(amb, "ForumId"), "ambassador post: %s",
          servoom_status_str(st));
    cJSON_Delete(amb);

    /* Inbox and own lists: must answer, may be empty. */
    cJSON *unread = NULL;
    st = servoom_client_unread_counts(c, &unread);
    CHECK(st == SERVOOM_OK && unread && cJSON_GetObjectItemCaseSensitive(unread, "LikeUnReadCnt"), "unread counts: %s",
          servoom_status_str(st));
    cJSON_Delete(unread);
    cJSON *nc = NULL;
    st = servoom_client_notify_config(c, &nc);
    CHECK(st == SERVOOM_OK && nc, "notify config: %s", servoom_status_str(st));
    cJSON_Delete(nc);
    n = 0;
    CHECK(servoom_client_list_like_notifications(c, 3, count_items, &n) == SERVOOM_OK, "like notifications");
    CHECK(servoom_client_list_comment_notifications(c, 3, count_items, &n) == SERVOOM_OK, "comment notifications");
    CHECK(servoom_client_list_follower_notifications(c, 3, count_items, &n) == SERVOOM_OK, "follower notifications");
    CHECK(servoom_client_list_my_followers(c, 3, count_items, &n) == SERVOOM_OK, "my followers");
    CHECK(servoom_client_list_my_following(c, 3, count_items, &n) == SERVOOM_OK, "my following");
    CHECK(servoom_client_list_my_likes(c, 3, NULL, count_items, &n) == SERVOOM_OK, "my likes");
    CHECK(servoom_client_list_blacklist(c, 3, count_items, &n) == SERVOOM_OK, "blacklist");
    CHECK(servoom_client_list_letters(c, 3, count_items, &n) == SERVOOM_OK, "letters");
    CHECK(servoom_client_list_my_playlists(c, 3, count_items, &n) == SERVOOM_OK, "my playlists");
    cJSON *conv = NULL;
    CHECK(servoom_client_conversations(c, &conv) == SERVOOM_OK && conv, "conversations");
    cJSON_Delete(conv);
    cJSON *groups = NULL;
    st = servoom_client_chat_groups(c, &groups);
    CHECK(st == SERVOOM_OK && groups && cJSON_GetArraySize(groups) > 0 &&
              cJSON_GetObjectItemCaseSensitive(cJSON_GetArrayItem(groups, 0), "ClassifyName"),
          "chat groups flattened with ClassifyName: %s", servoom_status_str(st));
    cJSON_Delete(groups);

    /* Legacy server-side render of a 16x16 file from the feed (may be empty for modern files). */
    cJSON *prev = NULL;
    st = servoom_client_legacy_preview(c, gallery_id, NULL, &prev);
    CHECK(st == SERVOOM_OK && prev && cJSON_GetObjectItemCaseSensitive(prev, "PicCount"), "legacy preview: %s",
          servoom_status_str(st));
    cJSON_Delete(prev);

    servoom_client_free(c);
    return tl_finish("test_live");
#endif
}
