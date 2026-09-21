/* Live cloud-client test. Needs SERVOOM_EMAIL and SERVOOM_PASSWORD (or
 * SERVOOM_MD5_PASSWORD) in the environment; otherwise it is skipped (exit 77).
 *
 * Logs in, lists the account's own uploads (may be empty), pages a public category feed,
 * fetches gallery info for the first item, downloads its artwork file and decodes it. No
 * particular artwork or user is hard-coded. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "servoom/servoom.h"
#include "testlib.h"

static int count_items(const cJSON *item, void *ud)
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
    st = servoom_client_list_my_uploads(c, 5, NULL, count_items, &mine);
    CHECK(st == SERVOOM_OK, "my uploads listing: %s (%s)", servoom_status_str(st), servoom_client_last_error(c));

    /* Public feed ("New" category), limited. */
    int n = 0;
    st = servoom_client_list_category(c, 0, 5, NULL, count_items, &n);
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
    servoom_client_free(c);
    return tl_finish("test_live");
#endif
}
