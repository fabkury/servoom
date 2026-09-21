/* Live cloud-client test. Needs SERVOOM_EMAIL and SERVOOM_PASSWORD (or
 * SERVOOM_MD5_PASSWORD) in the environment; otherwise it is skipped (exit 77).
 *
 * Logs in, fetches gallery info for artwork 4164515 (the format-26 sample bundled under
 * reference-animations/), lists a few items of a category feed, downloads the artwork and
 * decodes it, checking the pixels against the Python regression baseline. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "servoom/servoom.h"
#include "testlib.h"

#define GALLERY_ID 4164515
#define GALLERY_HASH "8c2743efe7514d0054b972a89b50802f0fcd286c21bb3538dd47396f13cb9a89"

static int count_items(const cJSON *item, void *ud)
{
    int *n = (int *)ud;
    (*n)++;
    CHECK(cJSON_IsObject(item) && cJSON_GetObjectItemCaseSensitive(item, "GalleryId"), "item has GalleryId");
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

    cJSON *info = NULL;
    st = servoom_client_gallery_info(c, GALLERY_ID, &info);
    if (CHECK(st == SERVOOM_OK && info, "gallery info: %s", servoom_status_str(st))) {
        const cJSON *fid = cJSON_GetObjectItemCaseSensitive(info, "FileId");
        CHECK(cJSON_IsString(fid) && strlen(fid->valuestring) > 10, "FileId present");
        CHECK(cJSON_GetObjectItemCaseSensitive(info, "LayerFileId") != NULL, "LayerFileId present");
        cJSON_Delete(info);
    }
    cJSON *bad = NULL;
    st = servoom_client_gallery_info(c, 1, &bad);
    CHECK(st == SERVOOM_ERR_API && bad == NULL, "bogus gallery id -> api error (%s)", servoom_status_str(st));

    int n = 0;
    st = servoom_client_list_category(c, 0, 5, NULL, count_items, &n);
    CHECK(st == SERVOOM_OK && n == 5, "category listing limit 5: %s, n=%d", servoom_status_str(st), n);

    cJSON *arr = NULL;
    st = servoom_client_collect_someone_uploads(c, 404758565, 3, &arr);
    CHECK(st == SERVOOM_OK && arr && cJSON_GetArraySize(arr) == 3, "someone uploads collected: %s",
          servoom_status_str(st));
    cJSON_Delete(arr);

    char *path = NULL;
    st = servoom_client_download_artwork(c, GALLERY_ID, "live-test-downloads", &path, NULL);
    if (CHECK(st == SERVOOM_OK && path, "download artwork: %s (%s)", servoom_status_str(st),
              servoom_client_last_error(c))) {
        servoom_pixel_bean *bean = NULL;
        st = servoom_decode_file(path, &bean);
        if (CHECK(st == SERVOOM_OK, "decode downloaded artwork: %s", servoom_status_str(st))) {
            char hex[65];
            tl_bean_hash(bean, hex);
            CHECK(bean->total_frames == 15 && bean->width == 128 && bean->speed == 100, "artwork shape");
            CHECK(strcmp(hex, GALLERY_HASH) == 0, "artwork pixels match python baseline");
            servoom_pixel_bean_free(bean);
        }
        remove(path);
        free(path);
    }
    servoom_client_free(c);
    return tl_finish("test_live");
#endif
}
